import machine
from machine import Pin, SPI, PWM  # 하드웨어 제어를 위한 필수 모듈들
import struct  # BMP 파일의 바이너리 데이터를 해석하기 위해 필요
import time    # 시간 지연(sleep) 등을 위해 필요
import st7735  # 업로드하신 TFT 구동 라이브러리

# ==========================================
# 1. 하드웨어(SPI 및 핀) 설정
# ==========================================

# SPI 설정: 데이터를 화면으로 빠르게 쏘아주는 통신 방식입니다.
# - baudrate=20000000: 통신 속도 (20MHz). 화면 갱신이 느리면 이 값을 조절합니다.
# - sck=Pin(18): 클럭 신호 (박자 맞추기)
# - mosi=Pin(23): 데이터 전송 (Master Out Slave In)
# - miso는 화면에서 데이터를 읽어올 일이 거의 없으므로 설정하지 않아도 됩니다.
spi = SPI(2, baudrate=20000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(23))

# 백라이트(BLK) 설정 (요청하신 2번 핀)
# 단순히 켜고 끄는 것보다 PWM(펄스 폭 변조)을 쓰면 밝기 조절이 가능합니다.
blk = PWM(Pin(2))
blk.freq(1000)      # 1초에 1000번 깜빡임 (눈에는 안 보임, 그냥 켜진 것처럼 보임)
blk.duty(1023)      # 밝기 설정 (0: 꺼짐 ~ 1023: 최대 밝기)
                    # 너무 눈부시면 512 정도로 줄여보세요.

# ==========================================
# 2. TFT 화면 초기화
# ==========================================

# 라이브러리 객체 생성
# - spi: 위에서 만든 통신 객체
# - 16: DC 핀 (Data/Command 구분 핀)
# - 17: RST 핀 (리셋 핀)
# - 5:  CS 핀 (Chip Select, 화면 선택 핀)
tft = st7735.TFT(spi, 16, 17, 5)

# 초기화 명령 실행 (Red Tab 버전 초기화)
# 화면에 노이즈가 끼거나 밀리면 initb(), initg() 등으로 바꿔봐야 합니다.
tft.initr()

# 색상 보정 설정
tft.invertcolor(False) # 색상이 반전(네거티브)되어 보이면 True로 변경
tft.rgb(True)          # 빨강(R)과 파랑(B)이 서로 바뀌어 나오면 False로 변경

# 화면 깨끗하게 지우기 (검은색 배경)
tft.fill(st7735.TFT.BLACK)


# ==========================================
# 3. BMP 이미지 그리기 함수
# ==========================================
def draw_bmp_32(filename):
    try:
        # 'rb'는 읽기(Read) + 바이너리(Binary) 모드입니다.
        with open(filename, "rb") as f:
            # BMP 파일인지 헤더 확인 ('BM'이라는 글자로 시작해야 함)
            if f.read(2) != b'BM':
                print("BMP 파일이 아닙니다.")
                return

            # --- 헤더 정보 읽기 ---
            # seek(위치): 파일 내에서 커서를 해당 위치로 이동시킵니다.
            # struct.unpack: 바이너리 데이터를 우리가 아는 숫자로 변환합니다.
            
            f.seek(10) # 데이터가 시작되는 위치(Offset) 정보가 있는 곳
            offset = struct.unpack("<I", f.read(4))[0]
            
            f.seek(18) # 가로(Width), 세로(Height) 정보가 있는 곳
            width = struct.unpack("<I", f.read(4))[0]
            height = struct.unpack("<I", f.read(4))[0]
            
            f.seek(28) # 비트 깊이 (24비트인지 32비트인지) 정보
            bit_depth = struct.unpack("<H", f.read(2))[0]
            
            # 지원하지 않는 형식이면 중단
            if bit_depth not in [24, 32]:
                print(f"{bit_depth}비트는 지원하지 않습니다.")
                return

            bytes_per_pixel = bit_depth // 8 # 픽셀 하나당 몇 바이트인지 (3 or 4)
            print(f"이미지: {width}x{height}, {bit_depth}bit")
            
            # 실제 픽셀 데이터가 있는 곳으로 점프
            f.seek(offset)
            
            # --- 이미지 그리기 루프 ---
            # BMP 파일은 보통 이미지가 '거꾸로(바닥부터 위로)' 저장되어 있습니다.
            # 그래서 y값을 height-1 부터 0까지 거꾸로 줄여나가며 읽습니다.
            for y in range(height - 1, -1, -1):
                
                # 한 줄(row)을 저장할 임시 버퍼 생성 (16비트 컬러이므로 폭 * 2바이트)
                row_data = bytearray(width * 2)
                
                for x in range(width):
                    # 파일에서 픽셀 하나(3바이트 혹은 4바이트)를 읽음
                    pixel = f.read(bytes_per_pixel)
                    if not pixel: break
                    
                    # BMP는 색상 순서가 B, G, R 순서로 저장되어 있습니다.
                    b, g, r = pixel[0], pixel[1], pixel[2]
                    
                    # [중요] 색상 변환 (RGB888 -> RGB565)
                    # PC 이미지는 24비트(8,8,8)인데, 이 화면은 16비트(5,6,5)만 받습니다.
                    # R에서 상위 5비트, G에서 6비트, B에서 5비트를 가져와 합칩니다.
                    color565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    
                    # 변환된 16비트 색상을 두 개의 8비트로 쪼개서 버퍼에 담습니다.
                    row_data[x * 2] = (color565 >> 8) & 0xFF # 상위 8비트
                    row_data[x * 2 + 1] = color565 & 0xFF    # 하위 8비트
                
                # 한 줄(Row)의 변환이 끝나면 화면에 그립니다.
                # 라이브러리의 image 함수를 사용하여 (x0, y0) ~ (x1, y1) 영역에 픽셀을 뿌립니다.
                tft.image(0, y, width - 1, y, row_data)
                
    except Exception as e:
        print("오류 발생:", e)

# ==========================================
# 4. 실행
# ==========================================
# 마이크로컨트롤러 안에 'image.bmp' 파일을 미리 넣어두셔야 합니다.
draw_bmp_32("bakhoon.bmp")