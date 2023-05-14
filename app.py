from flask import Flask, send_from_directory, render_template, request, jsonify
import os
import json
import sqlite3
import math
from functools import lru_cache


app = Flask(__name__)

rename_map = {"一只白白的白白": "最後一顆流星"}

@app.route('/')
def serve_login():
    return render_template('login.html')

@lru_cache(maxsize=1)
def collect_thread_info():
    thread_info_list = []

    for file in os.listdir('posts'):
        if file.startswith('post_') and file.endswith('.json'):
            with open("posts/" + file, 'r') as f:
                data = json.load(f)
                thread_info = data["thread_info"]
                if thread_info["author"] in rename_map:
                    thread_info["author"] = rename_map[thread_info["author"]]
                if thread_info["last_reply_by"] in rename_map:
                    thread_info["last_reply_by"] = rename_map[thread_info["last_reply_by"]]
                thread_info_list.append(thread_info)

    thread_info_list.sort(key=lambda x: x.get("order", 100))
    return thread_info_list

@lru_cache(maxsize=1)
def read_threads_from_file():
    with open('threads.json', 'r', encoding='utf-8') as f:
        threads = json.load(f)
    return threads

@app.route('/post')
def serve_post():
    pn = request.args.get('pn', default=1, type=int) // 50 + 1
    all_threads = read_threads_from_file()
    if pn == 1:
        data = collect_thread_info()
    else:
        start_index = (pn - 2) * 50
        end_index = (pn - 1) * 50
        data = all_threads[start_index:end_index]


    for thread_info in data:
        if thread_info["author"] in rename_map:
            thread_info["author"] = rename_map[thread_info["author"]]
        if thread_info["last_reply_by"] in rename_map:
            thread_info["last_reply_by"] = rename_map[thread_info["last_reply_by"]]

    return render_template('index.html', data=data, current_page=pn,
                           total_count=math.ceil(len(all_threads) / 50) + 1)

def get_connection():
    conn = sqlite3.connect('post_info.db')
    return conn

@lru_cache(maxsize=2048)
def load_post_data(post_id):
    try:
        with open(f'posts/post_{post_id}.json', 'r') as f:
            data = json.load(f)
            ret = data["post_info"]
    except FileNotFoundError:
        """
            I don't want to use post_info.db any more, I want to read from structual_post_2.db.
            the related code about manipulating this database is written below:    conn = sqlite3.connect('structual_posts_2.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = '''
        SELECT thread_id, post_no, title, content, user_name, author_link, date_time, old_image, user_sign_image
        FROM posts
        ORDER BY thread_id ASC, post_no ASC
    '''
    cursor.execute(query)

    threads = {}
    for row in tqdm(cursor, desc="Processing data"):
        thread_id = row['thread_id']
        post = {
            "index": row['post_no'],
            "title": (row['title'] or '无标题') if row['post_no'] == 1 else "回复：" + (row['title'] or "无标题"),
            "content": row['content'],
            "author": row['user_name'],
            "author_link": ("https://tieba.baidu.com" + row['author_link']) if row['author_link'] is not None else None,
            "date": row['date_time'],
            "ip": None,
            "old_image": row['old_image'],
            "user_sign_image": row['user_sign_image'],
        }

        if thread_id not in threads:
            threads[thread_id] = []
        threads[thread_id].append(post)

        please change this block
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM post_info WHERE thread_id = ?', (post_id,))
            result = cursor.fetchone()
            if result:
                data = json.loads(result[0])
                ret = data
            else:
                raise Exception(f"Data for post_id {post_id} not found in JSON file or SQLite database.")
    
    for i in ret:
        if i["author"] in rename_map:
            i["author"] = rename_map[i["author"]]

    return ret

@app.route('/f')
def serve_content():
    post_id = request.args.get('kz', default=1, type=int)
    pn = request.args.get('pn', default=1, type=int) // 50 + 1
    all_data = load_post_data(post_id)
    data = all_data[(pn - 1) * 50 : pn * 50]
    return render_template('content.html', data=data, kz=post_id, current_page=pn,
                            total_count=len(all_data))

@app.route('/content2_files/<path:filename>')
def serve_static_files_2(filename):
    static_files_path = os.path.join(os.path.abspath('.'), 'content2_files')
    return send_from_directory(static_files_path, filename)

@app.route('/login_files/<path:filename>')
def serve_static_files_3(filename):
    static_files_path = os.path.join(os.path.abspath('.'), 'login_files')
    return send_from_directory(static_files_path, filename)


@app.route('/百度贴吧_嘻哈小天才吧_files/<path:filename>')
def serve_static_files(filename):
    static_files_path = os.path.join(os.path.abspath('.'), '百度贴吧_嘻哈小天才吧_files')
    return send_from_directory(static_files_path, filename)

@app.route('/static/<path:filename>')
def serve_static_files_x(filename):
    static_files_path = os.path.join(os.path.abspath('.'), 'static')
    return send_from_directory(static_files_path, filename)

DATABASE = 'submitted.db'


@app.route("/submit", methods=["POST"])
def handle_submit():
    if request.method == "POST":
        json_data = request.get_json()
        data = json_data["data"]

        with sqlite3.connect(DATABASE) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, data TEXT NOT NULL);''')
            count = conn.execute("SELECT COUNT(*) FROM submissions;").fetchone()[0]

            if count < 10000:
                conn.execute("INSERT INTO submissions (data) VALUES (?);", (data,))
                conn.commit()
                return jsonify({"message": "已提交，待审核。", "success": True})
            else:
                return jsonify({"message": "Database limit reached. Cannot save more data.", "success": False})

    return redirect("/")


@app.route('/filtered_posts')
def filtered_posts():
    user_name = request.args.get('user_name')
    thread_only = request.args.get('thread_only', 'false') == 'true'
    conn = sqlite3.connect('structual_posts_2.db')
    conn.row_factory = sqlite3.Row  # Set the row_factory to sqlite3.Row
    cur = conn.cursor()

    if thread_only:
        cur.execute('SELECT * FROM posts WHERE user_name=? AND post_no=1 order by date_time desc', (user_name,))
    else:
        cur.execute('SELECT * FROM posts WHERE user_name=? order by date_time desc', (user_name,))

    posts = cur.fetchall()
    conn.close()
    return render_template('filtered_posts.html', posts=posts, user_name=user_name, thread_only=thread_only)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5003)
