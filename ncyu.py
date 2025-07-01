import sensor, image, time
from os import listdir
from pyb import UART

uart = UART(3, 115200)

label_result  = image.Image("./chinese/result565.bmp",  copy_to_fb=False)
label_capture = image.Image("./chinese/capture565.bmp", copy_to_fb=False)

TRANS_result = label_result.get_pixel(0, 0)
TRANS_capture = label_capture.get_pixel(0, 0)

def show_chinese(background_img, label_img, pos_x, pos_y, transparent_color):
    for y in range(label_img.height()):
        for x in range(label_img.width()):
            pixel = label_img.get_pixel(x, y)
            if pixel != transparent_color:
                background_img.set_pixel(pos_x + x, pos_y + y, pixel)

library_alphanumeric = listdir('./testpgm')
library_alphanumeric.sort()
alphanumeric_template = []

for n in range(len(library_alphanumeric)):
    alphanumeric_template.append(image.Image('./testpgm/' + library_alphanumeric[n]))

license_number = [' ' for _ in range(7)]

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.set_windowing((320, 172))
sensor.set_contrast(2)
sensor.set_vflip(False)
sensor.set_hmirror(False)

clock = time.clock()

img_GRAYSCALE = sensor.alloc_extra_fb(320, 172, sensor.GRAYSCALE)
img_GRAYSCALE_2 = sensor.alloc_extra_fb(320, 172, sensor.GRAYSCALE)
img_targets = []
for _ in range(7):
    img_targets.append(sensor.alloc_extra_fb(30, 40, sensor.GRAYSCALE))

def draw_outline_string(img, x, y, s, col, scale=2):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                img.draw_string(x+dx, y+dy, s, color=(0,0,0), scale=scale, mono_space=False, x_spacing=0)

    img.draw_string(x, y, s, color=col, scale=scale, mono_space=False, x_spacing=0)

while True:
    clock.tick()
    img = sensor.snapshot()
    img_GRAYSCALE.draw_image(img, 0, 0)
    img_GRAYSCALE_2.draw_image(img_GRAYSCALE, 0, 0)

    img_GRAYSCALE.laplacian(1)
    img_GRAYSCALE.gamma_corr(gamma=1.2, contrast=25)

    blobs = img_GRAYSCALE.find_blobs(
        [(0, 80)],
        x_stride=2, y_stride=1,
        pixels_threshold=80,
        area_threshold=80,
        margin=10
    )

    target_blobs = []
    for i in range(len(blobs)):
        find_out_times = 0
        for j in range(len(blobs)):
            if (abs(blobs[i].h() - blobs[j].h()) < blobs[i].h() * 0.2) and \
               (abs(blobs[i].cy() - blobs[j].cy()) < blobs[i].h() * 0.3):
                find_out_times += 1
                if find_out_times > 4:
                    target_blobs.append(blobs[i])
                    break

    target_blobs.sort(key=lambda b: b.y())

    line_ending = []
    for i in range(len(target_blobs) - 1):
        if abs(target_blobs[i].cy() - target_blobs[i + 1].cy()) > target_blobs[i].h() * 0.3:
            line_ending.append(i)
    line_ending.append(len(target_blobs))

    target_blob_lines = []
    if line_ending and line_ending != [0]:
        for i in range(len(line_ending)):
            if i == 0:
                if line_ending[i] - 0 > 5:
                    tmp_line = target_blobs[:line_ending[i]]
                    tmp_line.sort(key=lambda b: b.x())
                    target_blob_lines.append(tmp_line)
            else:
                if line_ending[i] - line_ending[i - 1] > 5:
                    tmp_line = target_blobs[line_ending[i - 1] + 1:line_ending[i]]
                    tmp_line.sort(key=lambda b: b.x())
                    target_blob_lines.append(tmp_line)

    while True:
        changed = False
        for line in target_blob_lines:
            if len(line) >= 3:
                if ((line[-2].cx() - line[-3].cx()) * 0.8 <
                    (line[-1].cx() - line[-2].cx()) >
                    (line[-2].cx() - line[-3].cx()) * 1.2):
                    del line[-1]
                    changed = True
                    break
        if not changed:
            break

    for i in range(len(target_blob_lines)):
        if len(target_blob_lines[i]) > 7:
            del target_blob_lines[i][0: len(target_blob_lines[i]) - 7]

    target_blob_max = None
    if target_blob_lines:
        target_blob_max = max(target_blob_lines, key=lambda b: b[0].pixels())

    if target_blob_max:
        try:
            for idx, b in enumerate(target_blob_max):
                img_targets[idx].clear()
                scale_x = 33.0 / b.h()
                scale_y = 33.0 / b.h()
                roi = (b.x() - 2, b.y() - 2, b.w() + 20, b.h() + 20)
                img_targets[idx].draw_image(img_GRAYSCALE_2, 0, 0,
                                            x_scale=scale_x, y_scale=scale_y,
                                            roi=roi)
                img.draw_rectangle(b.rect(), color=(255, 0, 0))
            for idx in range(len(target_blob_max)):
                img.draw_image(img_targets[idx], x=115 + idx*24, y=135, x_scale=0.75, y_scale=0.75)

        except:
            pass

        for i in range(len(target_blob_max)):
            matching_rate = 0.75

            while True:
                found_candidates = []

                for t in range(len(alphanumeric_template)):
                    found_blobs = img_targets[i].find_template(
                        alphanumeric_template[t],
                        matching_rate,
                        step=2,
                        search=image.SEARCH_EX
                    )

                    if found_blobs:
                        for fb in found_blobs:
                            if isinstance(fb, (list, tuple)) and len(fb) > 0:
                                score = fb[-1]
                            else:
                                score = 0

                            found_candidates.append(
                                (library_alphanumeric[t][:-4], score)
                            )

                if len(found_candidates) == 0:
                    if matching_rate > 0.4:
                        matching_rate -= 0.05
                        continue
                    else:
                        break

                found_candidates.sort(key=lambda x: x[1], reverse=True)
                best_char, best_score = found_candidates[0]
                license_number[i] = best_char
                break

        result_str = ''.join(license_number)
        red_scale = 4
        red_offset = 70
        red_x = (320 - len(result_str)*8*red_scale)//2 + red_offset
        draw_outline_string(img, red_x, 5, result_str, (255,0,0), scale=red_scale)

        show_chinese(img, label_result, 0, 5, TRANS_result)
        show_chinese(img, label_capture, 0, 130, TRANS_capture)

        print(license_number)
        uart.write(''.join(license_number) + '\r\n')
