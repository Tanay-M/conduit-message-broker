def auth_app(conn, api_key):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM fn_auth_app(%s::uuid)", (api_key,))
        return cur.fetchone()
