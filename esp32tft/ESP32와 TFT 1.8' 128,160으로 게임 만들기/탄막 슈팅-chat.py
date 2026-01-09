import machine
from machine import Pin, ADC, SPI, PWM
import st7735 #https://github.com/boochow/MicroPython-ST7735/blob/master/ST7735.py
import time
import random

# ============================================================
#                      하드웨어 설정
# ============================================================

# SPI로 ST7735 TFT 연결
spi = SPI(
    2,
    baudrate=40000000,
    polarity=0,
    phase=0,
    sck=Pin(18),
    mosi=Pin(23)
)

# TFT 초기화 (CS=16, DC=17, RST=5)
tft = st7735.TFT(spi, 16, 17, 5)
tft.initr()
tft.rgb(True)

# 백라이트 PWM 제어
blk = PWM(Pin(2))
blk.freq(1000)
blk.duty(1023)

# 조이스틱 아날로그 입력
joy_x = ADC(Pin(34))
joy_y = ADC(Pin(35))
joy_x.atten(ADC.ATTN_11DB)
joy_y.atten(ADC.ATTN_11DB)

# 발사 버튼
btn_fire = Pin(33, Pin.IN)

# ============================================================
#                        상수 정의
# ============================================================

CENTER   = 2048       # 조이스틱 중앙값
DEADZONE = 1000       # 흔들림 방지 데드존

SCREEN_W = 128
SCREEN_H = 160

# 자주 쓰는 색상 캐싱 (속도 향상)
BLACK  = st7735.TFT.BLACK
RED    = st7735.TFT.RED
WHITE  = st7735.TFT.WHITE
GREEN  = st7735.TFT.GREEN
CYAN   = st7735.TFT.CYAN
YELLOW = st7735.TFT.YELLOW
MAROON = st7735.TFT.MAROON

# ============================================================
#                5x5 픽셀 폰트 (GAME OVER)
# ============================================================

font_map = {
    'G':[0b01110,0b10000,0b10111,0b10001,0b01110],
    'A':[0b01110,0b10001,0b11111,0b10001,0b10001],
    'M':[0b10001,0b11011,0b10101,0b10001,0b10001],
    'E':[0b11111,0b10000,0b11110,0b10000,0b11111],
    'O':[0b01110,0b10001,0b10001,0b10001,0b01110],
    'V':[0b10001,0b10001,0b10001,0b01010,0b00100],
    'R':[0b11110,0b10001,0b11110,0b10100,0b10010],
    ' ':[0]*5
}

def draw_pixel_text(text, x, y, color, size=1):
    """
    5x5 비트맵 폰트를 size 배율로 화면에 출력
    """
    cx = x
    for ch in text:
        bitmap = font_map.get(ch)
        if bitmap:
            for i, col in enumerate(bitmap):
                for j in range(5):
                    if col & (1 << j):
                        tft.fillrect(
                            (cx+i*size, y+j*size),
                            (size, size),
                            color
                        )
        cx += 6 * size

# ============================================================
#                  충돌 판정 함수
# ============================================================

def hit(ax, ay, bx, by, r):
    """
    사각형 기반 간단 충돌 판정
    (원형보다 빠르고 픽셀 게임에 충분)
    """
    return abs(ax-bx) < r and abs(ay-by) < r

# ============================================================
#                     메인 게임 루프
# ============================================================

while True:  # 게임 재시작 루프
    tft.fill(BLACK)

    # ---------------- 플레이어 상태 ----------------
    p_x, p_y = 64, 140         # 현재 위치
    old_px, old_py = p_x, p_y # 이전 위치 (잔상 제거용)
    p_speed = 2

    # ---------------- 오브젝트 리스트 ----------------
    bullets = []   # [x, y, old_y, speed]
    enemies = []   # [x, y, old_y, hp, stop_y, size, spawn_time]
    ebullets = []  # [x, y, old_y]

    # ---------------- 타이머 ----------------
    last_shot  = 0
    last_enemy = 0

    game_over = False

    # ========================================================
    #                     프레임 루프
    # ========================================================
    while not game_over:
        now = time.ticks_ms()

        # ----------------------------------------------------
        # 1. 입력 처리 (조이스틱)
        # ----------------------------------------------------
        vx = joy_x.read()
        vy = joy_y.read()

        old_px, old_py = p_x, p_y
        moving_up = False

        if vx < CENTER-DEADZONE:
            p_x -= p_speed
        elif vx > CENTER+DEADZONE:
            p_x += p_speed

        if vy < CENTER-DEADZONE:
            p_y -= p_speed
            moving_up = True
        elif vy > CENTER+DEADZONE:
            p_y += p_speed

        # 화면 밖으로 못 나가게 제한
        p_x = min(122, max(5, p_x))
        p_y = min(154, max(5, p_y))

        # ----------------------------------------------------
        # 2. 플레이어 발사 처리
        # ----------------------------------------------------
        if btn_fire.value() and time.ticks_diff(now, last_shot) > 180:
            bullets.append([
                p_x,
                p_y - 5,
                p_y - 5,
                10 + (p_speed if moving_up else 0)
            ])
            last_shot = now

        # ----------------------------------------------------
        # 3. 적 생성 로직
        # ----------------------------------------------------
        if len(enemies) < 3 and time.ticks_diff(now, last_enemy) > 1500:
            size = random.randint(8, 13)

            # 크기에 따라 체력 결정
            hp = 1 if size < 10 else (2 if size < 12 else 4)

            y = -10  # 화면 위에서 등장
            enemies.append([
                random.randint(15, 110),
                y, y, hp,
                random.randint(20, 50),
                size,
                now
            ])
            last_enemy = now

        # ----------------------------------------------------
        # 4. 아군 총알 처리
        # ----------------------------------------------------
        new_bullets = []
        for b in bullets:
            x, y, old_y, speed = b

            # 이전 프레임 총알 삭제
            tft.fillrect((x, old_y), (2, 4), BLACK)

            # 이동
            y -= speed
            if y <= 0:
                continue

            # 적과 충돌 검사
            hit_flag = False
            for e in enemies:
                if hit(x, y, e[0], e[1], e[5]//2):
                    e[3] -= 1  # 적 HP 감소
                    hit_flag = True
                    break

            if not hit_flag:
                tft.fillrect((x, y), (2, 4), YELLOW)
                new_bullets.append([x, y, y, speed])

        bullets = new_bullets

        # ----------------------------------------------------
        # 5. 적 이동 / 공격 / 충돌
        # ----------------------------------------------------
        new_enemies = []
        for e in enemies:
            x, y, old_y, hp, stop_y, size, born = e
            half = size // 2

            # 이전 위치 제거 (잔상 방지 핵심)
            tft.fillrect((x-half, old_y-half), (size, size), BLACK)

            # 10초 후 자폭 돌진 상태
            charging = time.ticks_diff(now, born) > 10000

            if charging:
                y += 4
            elif y < stop_y:
                y += 1

            # 플레이어 충돌 / 화면 밖
            if hit(p_x, p_y, x, y, half+3) or y > SCREEN_H:
                game_over = True
                continue

            # 적 총알 발사
            if not charging and random.randint(1, 60) == 1:
                ebullets.append([x, y+half, y+half])

            # 살아있으면 다시 그림
            if hp > 0:
                color = MAROON if charging else (GREEN if hp == 1 else CYAN)
                tft.fillrect((x-half, y-half), (size, size), color)
                new_enemies.append([x, y, y, hp, stop_y, size, born])

        enemies = new_enemies

        # ----------------------------------------------------
        # 6. 적 총알 처리
        # ----------------------------------------------------
        new_eb = []
        for eb in ebullets:
            x, y, old_y = eb

            # 이전 위치 삭제
            tft.fillrect((x, old_y), (2, 2), BLACK)

            y += 4

            if hit(p_x, p_y, x, y, 4):
                game_over = True
                continue

            if y < SCREEN_H:
                tft.fillrect((x, y), (2, 2), WHITE)
                new_eb.append([x, y, y])

        ebullets = new_eb

        # ----------------------------------------------------
        # 7. 플레이어 그리기
        # ----------------------------------------------------
        tft.fillrect((old_px-2, old_py-2), (5, 5), BLACK)
        tft.fillrect((p_x-2, p_y-2), (5, 5), RED)

        time.sleep_ms(10)

    # ========================================================
    #                    GAME OVER 화면
    # ========================================================
    tft.fill(RED)
    tft.fillrect((0, 65), (128, 30), BLACK)
    draw_pixel_text("GAME OVER", 12, 72, WHITE, 2)

    time.sleep(1)
    while not btn_fire.value():
        time.sleep_ms(100)
