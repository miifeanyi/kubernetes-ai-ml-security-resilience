
import json, secrets, socket, struct, sys
transport, resolver, expected = sys.argv[1:]
name = "inference.n1-serving.svc.cluster.local"
qid = secrets.randbits(16)
question = b"".join(bytes([len(s)]) + s.encode() for s in name.split("."))
question += b"\0" + struct.pack("!HH", 1, 1)
query = struct.pack("!6H", qid, 0x0100, 1, 0, 0, 0) + question

def exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ValueError("short reply")
        data += chunk
    return data

def skip_name(data, offset):
    while True:
        size = data[offset]
        offset += 1
        if size == 0:
            return offset
        if size & 0xc0 == 0xc0:
            return offset + 1
        if size > 63:
            raise ValueError("invalid label")
        offset += size

try:
    kind = socket.SOCK_DGRAM if transport == "UDP" else socket.SOCK_STREAM
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.settimeout(2)
        sock.connect((resolver, 53))
        if transport == "UDP":
            sock.send(query)
            data = sock.recv(4096)
        else:
            sock.sendall(struct.pack("!H", len(query)) + query)
            size = struct.unpack("!H", exact(sock, 2))[0]
            data = exact(sock, size)
    rid, flags, questions, answers, _, _ = struct.unpack_from("!6H", data)
    valid = (rid == qid and flags & 0x820f == 0x8000 and questions == 1
             and data[12:12 + len(question)] == question)
    offset = 12 + len(question)
    addresses = []
    for _ in range(answers):
        offset = skip_name(data, offset)
        typ, cls, ttl, size = struct.unpack_from("!HHIH", data, offset)
        offset += 10
        if typ == 1 and cls == 1 and size == 4:
            addresses.append(socket.inet_ntoa(data[offset:offset + size]))
        offset += size
    result = {"result": "allow" if valid and addresses == [expected]
              else "wrong-answer", "addresses": addresses}
except TimeoutError:
    result = {"result": "timeout"}
except Exception as exc:
    result = {"result": "error", "error": type(exc).__name__}
print(json.dumps(result))
