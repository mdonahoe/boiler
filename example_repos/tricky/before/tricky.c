#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int zero() {
    return 0;
}

int main(void) {
    if (zero() > 0) {
        printf("This can't happen");
    } else {
        printf("Tricky!\n");
    }
    return 0;
}
