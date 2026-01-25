import streamlit as st
from supabase import create_client, Client

# 1. Supabase のクライアント初期化
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("✅ Supabase Todo App")

# 2. タスクの追加機能
with st.form("add_todo", clear_on_submit=True):
    new_task = st.text_input("新しいタスクを入力してください")
    submit_button = st.form_submit_button("追加")

    if submit_button and new_task:
        # データの挿入
        supabase.table("todos").insert({"task": new_task}).execute()
        st.success("タスクを追加しました！")

# 3. タスクの表示と更新
st.subheader("現在のタスク一覧")
# データの取得（作成日時順）
response = supabase.table("todos").select("*").order("created_at").execute()
todos = response.data

for todo in todos:
    col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
    
    # 完了状態のチェックボックス
    is_done = col1.checkbox("", value=todo["is_complete"], key=f"check_{todo['id']}")
    
    # チェック状態が変わった場合にDBを更新
    if is_done != todo["is_complete"]:
        supabase.table("todos").update({"is_complete": is_done}).eq("id", todo["id"]).execute()
        st.rerun()

    # タスク名の表示（完了済みは打ち消し線風に）
    task_text = f"~~{todo['task']}~~" if todo["is_complete"] else todo["task"]
    col2.write(task_text)

    # 削除ボタン
    if col3.button("削除", key=f"del_{todo['id']}"):
        supabase.table("todos").delete().eq("id", todo["id"]).execute()
        st.rerun()