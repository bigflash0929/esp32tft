import machine
from machine import Pin, ADC, SPI, PWM
import st7735
import time
import random

# --- 하드웨어 설정 ---
spi = SPI(2, baudrate=40000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(23))
tft = st7735.TFT(spi, 16, 17, 5)
tft.initr()
tft.rgb(True)

blk = PWM(Pin(2)); blk.freq(1000); blk.duty(1023)
joy_x = ADC(Pin(34)); joy_y = ADC(Pin(35)); joy_x.atten(ADC.ATTN_11DB)
btn_fire = Pin(33, Pin.IN)

CENTER = 2048
DEADZONE = 1000

# --- 5x5 픽셀 폰트 데이터 (게임 오버 문구용) ---
font_map = {
    'G': [0b01110, 0b10000, 0b10111, 0b10001, 0b01110],
    'A': [0b01110, 0b10001, 0b11111, 0b10001, 0b10001],
    'M': [0b10001, 0b11011, 0b10101, 0b10001, 0b10001],
    'E': [0b11111, 0b10000, 0b11110, 0b10000, 0b11111],
    'O': [0b01110, 0b10001, 0b10001, 0b10001, 0b01110],
    'V': [0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    'R': [0b11110, 0b10001, 0b11110, 0b10100, 0b10010],
    'S': [0b01111, 0b10000, 0b01110, 0b00001, 0b11110],
    'T': [0b11111, 0b00100, 0b00100, 0b00100, 0b00100],
    ' ': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000]
}

def draw_pixel_text(tft, text, x, y, color, size=1):
    curr_x = x
    for char in text.upper():
        if char in font_map:
            bitmap = font_map[char]
            for i, col in enumerate(bitmap):
                for j in range(5):
                    if (col >> j) & 0x01:
                        tft.fillrect((curr_x + i*size, y + j*size), (size, size), color)
        curr_x += 6 * size

while True:  # [재시작 루프]
    tft.fill(st7735.TFT.BLACK)
    p_x, p_y = 64, 140
    old_x, old_y = p_x, p_y
    p_speed = 2
    
    bullets, enemies, enemy_bullets = [], [], []
    last_shot_time, last_enemy_time = 0, 0
    shot_delay, enemy_spawn_delay = 180, 1500 
    
    game_over = False

    while not game_over:
        current_time = time.ticks_ms()
        
        # 1. 조이스틱 입력 & 플레이어 이동
        vx, vy = joy_x.read(), joy_y.read()
        old_x, old_y = p_x, p_y
        moving_up = False
        if vx < (CENTER - DEADZONE): p_x -= p_speed
        elif vx > (CENTER + DEADZONE): p_x += p_speed
        if vy < (CENTER - DEADZONE): p_y -= p_speed; moving_up = True
        elif vy > (CENTER + DEADZONE): p_y += p_speed
        p_x, p_y = max(5, min(122, p_x)), max(5, min(154, p_y))
        
        # 2. 총알 발사
        if btn_fire.value() == 1:
            if time.ticks_diff(current_time, last_shot_time) > shot_delay:
                bullets.append([p_x, p_y - 5, 10 + (p_speed if moving_up else 0)])
                last_shot_time = current_time

        # 3. 적 생성
        if len(enemies) < 3 and time.ticks_diff(current_time, last_enemy_time) > enemy_spawn_delay:
            e_size = random.randint(8, 13)
            e_hp = 1 if e_size < 10 else (2 if e_size < 12 else 4)
            enemies.append([random.randint(15, 110), -10, e_hp, random.randint(20, 50), e_size, current_time])
            last_enemy_time = current_time

        # 4. 아군 총알 이동 및 충돌
        new_bullets = []
        for b in bullets:
            tft.fillrect((b[0], b[1]), (2, 4), st7735.TFT.BLACK)
            b[1] -= b[2]
            hit = False
            for e in enemies:
                hit_box = (e[4] // 2) + 1
                if abs(b[0] - e[0]) < hit_box and abs(b[1] - e[1]) < hit_box:
                    e[2] -= 1 
                    hit = True
                    if e[2] <= 0: 
                        tft.fillrect((e[0]-e[4]//2, e[1]-e[4]//2), (e[4], e[4]), st7735.TFT.BLACK)
                        enemies.remove(e)
                    break
            if not hit and b[1] > 0:
                tft.fillrect((b[0], b[1]), (2, 4), st7735.TFT.YELLOW)
                new_bullets.append(b)
        bullets = new_bullets

        # 5. 적 이동 및 자폭 로직
        new_enemies = []
        for e in enemies:
            half = e[4] // 2
            tft.fillrect((e[0]-half, e[1]-half), (e[4], e[4]), st7735.TFT.BLACK)
            
            is_charging = time.ticks_diff(current_time, e[5]) > 10000 
            if is_charging: e[1] += 4 
            elif e[1] < e[3]: e[1] += 1
            
            if abs(p_x - e[0]) < (half + 3) and abs(p_y - e[1]) < (half + 3): game_over = True
            if e[1] > 165: game_over = True 
            
            if not is_charging and random.randint(1, 60) == 1:
                enemy_bullets.append([e[0], e[1] + half])
            
            color = st7735.TFT.MAROON if is_charging else (st7735.TFT.GREEN if e[2] == 1 else st7735.TFT.CYAN)
            tft.fillrect((e[0]-half, e[1]-half), (e[4], e[4]), color)
            new_enemies.append(e)
        enemies = new_enemies

        # 6. 적 총알 이동
        new_ebullets = []
        for eb in enemy_bullets:
            tft.fillrect((eb[0], eb[1]), (2, 2), st7735.TFT.BLACK)
            eb[1] += 4 
            if abs(p_x - eb[0]) < 4 and abs(p_y - eb[1]) < 4: game_over = True
            if eb[1] < 160:
                tft.fillrect((eb[0], eb[1]), (2, 2), st7735.TFT.WHITE)
                new_ebullets.append(eb)
        enemy_bullets = new_ebullets

        # 7. 플레이어 그리기
        if p_x != old_x or p_y != old_y:
            tft.fillrect((old_x - 2, old_y - 2), (5, 5), st7735.TFT.BLACK)
        tft.fillrect((p_x - 2, p_y - 2), (5, 5), st7735.TFT.RED)
        
        time.sleep(0.01)

    # --- 8. 게임 오버 화면 연출 ---
    tft.fill(st7735.TFT.RED)
    tft.fillrect((0, 65), (128, 30), st7735.TFT.BLACK) # 글자 배경 바
    draw_pixel_text(tft, "GAME OVER", 12, 72, st7735.TFT.WHITE, 2)
    
    time.sleep(1.0)
    while btn_fire.value() == 0: 
        time.sleep(0.1)