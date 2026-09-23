from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os

DATA_FILE = "users.json"

def load_users():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def write_users(users):
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=2)

def bad_name(name): return not isinstance(name, str) or not name.strip()

def bad_email(email): return not isinstance(email, str) or "@" not in email or "." not in email

class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def _body(self):
        # JSON body as a dict, or None (after sending a 400) if missing/malformed
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length))
            if isinstance(body, dict):
                return body
        except ValueError:
            pass
        self._send(400, {"message": "NOT VALID "})

    def _target(self, path):
        # For /users/<id>: returns (all_users, the_user), or sends a 404 and returns (None, None)
        parts = path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "users" or not parts[1].isdigit():
            self._send(404, {"message": f"Path {path} does not exist"})
            return None, None
        users = load_users()
        for user in users:
            if user["id"] == int(parts[1]):
                return users, user
        self._send(404, {"message": f"User {parts[1]} not found"})
        return None, None

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self._send(200, {"message": "Welcome to the LIAM user server"})
        if url.path == "/users":
            users = load_users()
            name = parse_qs(url.query).get("name")
            if name:
                users = [u for u in users if name[0].lower() in u["name"].lower()]
            return self._send(200, users)
        users, user = self._target(url.path)
        if user:
            self._send(200, user)

    def do_POST(self):
        if urlparse(self.path).path != "/create":
            return self._send(404, {"message": "Path does not exist"})
        body = self._body()
        if body is None:
            return
        if bad_name(body.get("name")) or bad_email(body.get("email")):
            return self._send(400, {"message": "A name and a valid email are required"})
        users = load_users()
        new_id = max((u["id"] for u in users), default=0) + 1  # not len + 1: deletes break that
        user = {"id": new_id, "name": body["name"].strip(), "email": body["email"]}
        users.append(user)
        write_users(users)
        self._send(201, user)

    def do_PUT(self):
        users, user = self._target(urlparse(self.path).path)
        body = self._body() if user else None
        if body is None:
            return
        email = body.get("email", "")
        if bad_name(body.get("name")) or (email != "" and bad_email(email)):
            return self._send(400, {"message": "A name is required, and email must be valid"})
        user_id = user["id"]
        user.clear()  # replace the whole record: anything not sent is gone
        user.update({"id": user_id, "name": body["name"].strip(), "email": email})
        write_users(users)
        self._send(200, user)

    def do_PATCH(self):
        users, user = self._target(urlparse(self.path).path)
        body = self._body() if user else None
        if body is None:
            return
        updates = {k: body[k] for k in ("name", "email") if k in body}
        if not updates:
            return self._send(400, {"message": "Send at least one of: name, email"})
        if ("name" in updates and bad_name(updates["name"])) or ("email" in updates and bad_email(updates["email"])):
            return self._send(400, {"message": "name or email is not valid"})
        user.update(updates)  # only the fields sent change
        write_users(users)
        self._send(200, user)

    def do_DELETE(self):
        users, user = self._target(urlparse(self.path).path)
        if user:
            users.remove(user)
            write_users(users)
            self._send(200, {"message": f"User {user['id']} deleted"})

if __name__ == "__main__":
    print("Server is running on http://localhost:8000")
    HTTPServer(("", 8000), Handler).serve_forever()

