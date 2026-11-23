/* ARM Linux guest for the offline check of the FX3 7.02 VDF calculators (build/lcd_fx3_qemu.py).
 * The driver supplies the leaf functions' bytes from cpapp-b.bin 7.02, stock and with lcd32dsq_fx3_v1 applied:
 *   fit.bin    0x1df458..0x1df4ec  fit mode (panel code, aspect) with its tables
 *   ratio*.bin 0x1df794..0x1df884  picture ratio (_, w | h << 16, panel, aspect, fit, out)
 *   dsq*.bin   0x1df680..0x1df794  de-squeeze (_, w | h << 16, panel, aspect, fit, out, accessor, device)
 * Each is position-independent: internal branches and tbb tables only; the de-squeeze function calls the accessor's slot 0x758. */
#include <stdint.h>
#include <stdio.h>

__asm__(".pushsection .text\n.balign 4\n.thumb\n"
        ".thumb_func\n.global vdf_fit\nvdf_fit:\n.incbin \"fit.bin\"\n.balign 4\n"
        ".thumb_func\n.global ratio_stock\nratio_stock:\n.incbin \"ratio_stock.bin\"\n.balign 4\n"
        ".thumb_func\n.global ratio_patched\nratio_patched:\n.incbin \"ratio_patched.bin\"\n.balign 4\n"
        ".thumb_func\n.global dsq_stock\ndsq_stock:\n.incbin \"dsq_stock.bin\"\n.balign 4\n"
        ".thumb_func\n.global dsq_patched\ndsq_patched:\n.incbin \"dsq_patched.bin\"\n.popsection\n");

extern unsigned vdf_fit(unsigned panel, unsigned aspect);
typedef void ratio_fn(unsigned r0, unsigned wh, unsigned panel, unsigned aspect, unsigned fit, uint16_t *out);
typedef void dsq_fn(unsigned r0, unsigned wh, unsigned panel, unsigned aspect, unsigned fit, uint16_t *out, void *acc, unsigned device);
extern ratio_fn ratio_stock, ratio_patched;
extern dsq_fn dsq_stock, dsq_patched;

static uint8_t code_byte[2];
static uint8_t *get_code(void *self) { (void)self; return code_byte; }
static unsigned get_zero(void *self) { (void)self; return 0; }
static void *vtable[0x800 / 4];
static struct { void **vt; } accessor = { vtable };

int main(void)
{
    char which[16];
    unsigned patched, w, h, panel, aspect, code;
    vtable[0x758 / 4] = (void *)get_code;
    vtable[0x698 / 4] = (void *)get_zero;
    while (scanf("%15s %u %u %u %u %u %u", which, &patched, &w, &h, &panel, &aspect, &code) == 7) {
        uint16_t out[4] = {0, 0, 0, 0};
        unsigned fit = vdf_fit(panel, aspect);
        if (which[0] == 'r')
            (patched ? ratio_patched : ratio_stock)(0, w | h << 16, panel, aspect, fit, out);
        else {
            code_byte[0] = (uint8_t)code;
            code_byte[1] = 1;
            (patched ? dsq_patched : dsq_stock)(0, w | h << 16, panel, aspect, fit, out, &accessor, 1);
        }
        printf("%u %u %u %u %u\n", fit, out[0], out[1], out[2], out[3]);
    }
    return 0;
}
