
import http.client, json, sys, uuid
request_id = uuid.uuid4().hex
connection = http.client.HTTPConnection(sys.argv[1], 8080, timeout=3)
try:
    connection.request("GET", "/", headers={"X-Lab-Request": request_id})
    response = connection.getresponse()
    body = response.read()
    passed = (response.status == 200 and body == b"lab-inference-ok\n"
              and response.getheader("X-Lab-Request") == request_id)
    print(json.dumps({"request_id": request_id, "status": response.status,
                      "marker_and_id_match": passed}))
    sys.exit(0 if passed else 2)
finally:
    connection.close()
