#include <stdio.h>
#include "functions.h"

int main(int argc, char **argv) {
  printf("This is a simple test.\n");
  printf("%d+%d=%d\n", 2, 3, sum(2,3));
  return 0;
}
