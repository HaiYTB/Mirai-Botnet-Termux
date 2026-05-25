// recon.cpp — Trinh sát hệ thống: system info, network, processes
// Usage: ./recon type=<system|network|process|all>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unistd.h>

static std::string get_param(int argc, char* argv[], const char* key, const char* def = "") {
    std::string prefix = std::string(key) + "=";
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        if (arg.find(prefix) == 0) return arg.substr(prefix.length());
    }
    return def;
}

static void run_and_print(const char* cmd, const char* label) {
    FILE* f = popen(cmd, "r");
    if (!f) return;
    std::fprintf(stdout, "\"%s\":\"", label);
    char buf[4096];
    bool first = true;
    while (fgets(buf, sizeof(buf), f)) {
        if (!first) std::fprintf(stdout, "\\n");
        // Strip trailing newline and escape
        size_t len = std::strlen(buf);
        while (len > 0 && (buf[len-1] == '\n' || buf[len-1] == '\r')) buf[--len] = '\0';
        for (size_t i = 0; i < len; ++i) {
            if (buf[i] == '"') std::fprintf(stdout, "\\\"");
            else if (buf[i] == '\\') std::fprintf(stdout, "\\\\");
            else std::fputc(buf[i], stdout);
        }
        first = false;
    }
    std::fprintf(stdout, "\"");
    pclose(f);
}

int main(int argc, char* argv[]) {
    std::string type = get_param(argc, argv, "type", "system");
    std::fprintf(stdout, "{");

    bool need_comma = false;

    if (type == "system" || type == "all") {
        if (need_comma) std::fprintf(stdout, ",");
        run_and_print("uname -a", "uname");
        std::fprintf(stdout, ",");
        run_and_print("cat /proc/cpuinfo 2>/dev/null | grep 'model name' | head -1 | cut -d: -f2-", "cpu");
        std::fprintf(stdout, ",");
        run_and_print("cat /proc/meminfo 2>/dev/null | grep 'MemTotal'", "memory");
        std::fprintf(stdout, ",");
        run_and_print("whoami", "user");
        std::fprintf(stdout, ",");
        run_and_print("id 2>/dev/null", "id");
        need_comma = true;
    }

    if (type == "network" || type == "all") {
        if (need_comma) std::fprintf(stdout, ",");
        run_and_print("ip addr 2>/dev/null || ifconfig 2>/dev/null", "interfaces");
        std::fprintf(stdout, ",");
        run_and_print("ip route 2>/dev/null || route -n 2>/dev/null", "routes");
        std::fprintf(stdout, ",");
        run_and_print("cat /etc/resolv.conf 2>/dev/null | grep nameserver", "dns");
        std::fprintf(stdout, ",");
        run_and_print("arp -a 2>/dev/null || cat /proc/net/arp 2>/dev/null", "arp");
        need_comma = true;
    }

    if (type == "process" || type == "all") {
        if (need_comma) std::fprintf(stdout, ",");
        run_and_print("ps aux 2>/dev/null || ps 2>/dev/null", "processes");
        need_comma = true;
    }

    std::fprintf(stdout, "}\n");
    return 0;
}
