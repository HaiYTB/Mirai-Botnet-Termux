// shell.cpp — Thực thi lệnh shell và trả output
// Usage: ./shell <command>
// Hoặc:   ./shell cmd=<command>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <signal.h>
#include <unistd.h>

static void timeout_handler(int) {
    _exit(124);
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::fprintf(stderr, "Usage: %s <shell_command>\n", argv[0]);
        return 1;
    }

    std::string cmd;
    if (argc >= 2) {
        cmd = argv[1];
        // Handle cmd= prefix
        if (cmd.find("cmd=") == 0) cmd = cmd.substr(4);
        // Join remaining args
        for (int i = 2; i < argc; ++i) {
            cmd += " ";
            cmd += argv[i];
        }
    }

    signal(SIGALRM, timeout_handler);
    alarm(60);

    FILE* f = popen(cmd.c_str(), "r");
    if (!f) {
        std::fprintf(stdout, "{\"error\": \"popen failed\"}\n");
        return 1;
    }

    char buf[4096];
    while (fgets(buf, sizeof(buf), f)) {
        std::fputs(buf, stdout);
    }

    int status = pclose(f);
    alarm(0);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
