import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# ========== DATABASE SETUP ==========
# This function runs once when the app starts, before any requests come in.
# It creates the tasks.db file (if it doesn't exist) and sets up the table structure.

def init_db():
    """
    Initialize the SQLite database:
    1. Connect to tasks.db (creates it if missing)
    2. Create the 'tasks' table if it doesn't exist
    3. Seed three example tasks (only if the table is empty)
    
    Why IF NOT EXISTS? So if we restart the app, it doesn't crash trying to recreate the table.
    Why seed only if empty? So the three examples don't multiply on every restart.
    """
    
    # sqlite3.connect() opens (or creates) a file called tasks.db in your current directory
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Create the 'tasks' table with three columns:
    # - id: INTEGER PRIMARY KEY AUTOINCREMENT — database auto-assigns unique IDs (1, 2, 3, ...)
    # - title: TEXT NOT NULL — stores the task name, must be provided
    # - done: BOOLEAN DEFAULT 0 — tracks completion (0 = false, 1 = true)
    # 
    # IF NOT EXISTS prevents error if the table already exists from a previous run.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done BOOLEAN DEFAULT 0
        )
    ''')
    
    # Check if the table is empty by counting rows
    cursor.execute('SELECT COUNT(*) FROM tasks')
    row_count = cursor.fetchone()[0]  # fetchone() returns a tuple; [0] gets the first (only) value
    
    # Only seed data if the table is empty (count == 0)
    # This prevents the three example tasks from being inserted every time the server restarts.
    if row_count == 0:
        # Use ? placeholders for parameterized queries (prevents SQL injection)
        # The database will auto-assign the id; we only provide title and done.
        cursor.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            ("Learn FastAPI", False)
        )
        cursor.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            ("Build CRUD API", False)
        )
        cursor.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            ("Push to GitHub", False)
        )
    
    # conn.commit() writes all changes (CREATE TABLE, INSERT) to the file on disk.
    # Without this, changes stay in memory and disappear on restart.
    conn.commit()
    
    # Close the connection so other parts of the code can open their own connections.
    conn.close()

# Call init_db() when the app starts, before any requests arrive.
# This happens once per server startup.
init_db()

# ========== DATA SCHEMAS ==========
# These Pydantic models validate incoming JSON from the client.
# They haven't changed from Assignment 1 — the database swap is transparent to the API.

class TaskCreate(BaseModel):
    """Schema for creating a new task (client sends only the title)"""
    title: str

class TaskUpdate(BaseModel):
    """Schema for updating a task (client can change title and/or done status)"""
    title: str = None  # Optional
    done: bool = None  # Optional

# ========== ROOT & HEALTH ==========
@app.get("/")
def read_root():
    """Describe the API and list available endpoints"""
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks", "/health"]
    }

@app.get("/health")
def health_check():
    """Health check endpoint — verifies the server and database are responding"""
    return {"status": "ok"}

# ========== READ ==========
@app.get("/tasks")
def get_all_tasks():
    """
    Fetch all tasks from the database.
    
    Flow:
    1. Connect to tasks.db
    2. Execute SELECT * to fetch all rows
    3. Convert each row tuple to a dict with keys: id, title, done
    4. Return the list of dicts as JSON
    """
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # SELECT * fetches all columns in order: id, title, done
    cursor.execute('SELECT id, title, done FROM tasks')
    
    # fetchall() returns a list of tuples: [(1, "Learn FastAPI", 0), (2, "Build CRUD API", 0), ...]
    rows = cursor.fetchall()
    
    conn.close()
    
    # Convert each tuple to a dict so FastAPI can return it as JSON
    # done is stored as 0/1 in SQLite; convert to bool for consistency
    tasks = [
        {"id": row[0], "title": row[1], "done": bool(row[2])}
        for row in rows
    ]
    
    return tasks

@app.get("/tasks/{id}")
def get_task(id: int):
    """
    Fetch a single task by id.
    
    Flow:
    1. Connect to database
    2. Use parameterized query to find task with matching id (safe from SQL injection)
    3. If found, return the task dict
    4. If not found, raise 404
    """
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # The ? is a placeholder; we pass id separately in a tuple
    # This keeps id as data, never as executable SQL code
    cursor.execute('SELECT id, title, done FROM tasks WHERE id = ?', (id,))
    
    # fetchone() returns a single tuple or None if no match
    row = cursor.fetchone()
    
    conn.close()
    
    if row is None:
        # No task with this id found
        raise HTTPException(status_code=404, detail={"error": f"Task {id} not found"})
    
    # Convert tuple to dict
    task = {"id": row[0], "title": row[1], "done": bool(row[2])}
    return task

# ========== CREATE ==========
@app.post("/tasks")
def create_task(task_input: TaskCreate):
    """
    Create a new task in the database.
    
    Flow:
    1. Validate title (not empty)
    2. Connect to database
    3. INSERT the new task (database auto-assigns id)
    4. Fetch the newly created task
    5. Return it with status 201
    """
    
    # Validation: title must not be empty or just whitespace
    if not task_input.title or not task_input.title.strip():
        raise HTTPException(status_code=400, detail={"error": "title cannot be empty"})
    
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # INSERT into tasks table with title and default done=False (0)
    # Parameterized query protects against SQL injection
    cursor.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (task_input.title, False)
    )
    
    # Save the insert to disk
    conn.commit()
    
    # The database auto-assigned an id; fetch it using lastrowid
    # This gives us the id of the row we just inserted
    new_id = cursor.lastrowid
    
    # Fetch the newly created task so we can return it
    cursor.execute('SELECT id, title, done FROM tasks WHERE id = ?', (new_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    # Convert to dict and return (FastAPI automatically sets status 201 for POST)
    task = {"id": row[0], "title": row[1], "done": bool(row[2])}
    return task

# ========== UPDATE ==========
@app.put("/tasks/{id}")
def update_task(id: int, task_input: TaskUpdate):
    """
    Update a task's title and/or done status.
    
    Flow:
    1. Check if task exists (if not, 404)
    2. Build SQL UPDATE with only the fields that were provided
    3. Execute the update
    4. Fetch and return the updated task
    """
    
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # First, check if the task exists
    cursor.execute('SELECT id, title, done FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": f"Task {id} not found"})
    
    # Build the UPDATE query dynamically based on what was provided
    updates = []
    params = []
    
    if task_input.title is not None:
        # Validation: title must not be empty
        if not task_input.title.strip():
            conn.close()
            raise HTTPException(status_code=400, detail={"error": "title cannot be empty"})
        updates.append("title = ?")
        params.append(task_input.title)
    
    if task_input.done is not None:
        updates.append("done = ?")
        params.append(task_input.done)
    
    # If nothing was provided to update, just return the task as-is
    if not updates:
        task = {"id": row[0], "title": row[1], "done": bool(row[2])}
        conn.close()
        return task
    
    # Add the id to the end of params for the WHERE clause
    params.append(id)
    
    # Build the full UPDATE query: "UPDATE tasks SET title = ?, done = ? WHERE id = ?"
    update_query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(update_query, params)
    
    # Save the update to disk
    conn.commit()
    
    # Fetch and return the updated task
    cursor.execute('SELECT id, title, done FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    
    conn.close()
    
    task = {"id": row[0], "title": row[1], "done": bool(row[2])}
    return task

# ========== DELETE ==========
@app.delete("/tasks/{id}")
def delete_task(id: int):
    """
    Delete a task by id.
    
    Flow:
    1. Check if task exists (if not, 404)
    2. DELETE the task
    3. Return 204 No Content (empty response, task is gone)
    """
    
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # First, check if the task exists
    cursor.execute('SELECT id FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": f"Task {id} not found"})
    
    # Delete the task
    cursor.execute('DELETE FROM tasks WHERE id = ?', (id,))
    
    # Save the deletion to disk
    conn.commit()
    
    conn.close()
    
    # Return None (FastAPI converts this to 204 No Content status)
    return None