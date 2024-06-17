// Type your code here, or load an example.
int main(int argc, char** argv) {
    int a=argv[0][0];
    return argc*a;
}

__attribute__((noreturn)) int _exit() {
  asm("ebreak");
}
