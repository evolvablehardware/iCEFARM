#include <stdio.h>
#include <stdbool.h>
#include "pico/stdlib.h"
#include "boards.h"
#include "tusb.h"

int main(void) {
    tusb_init();
    stdio_init_all();

    while (1) {
        tud_task();
        printf("default firmware\r\n");
        getchar_timeout_us(1000);
    }
    return 0;
}
