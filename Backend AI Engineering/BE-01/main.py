from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# ========== DATABASE (IN-MEMORY) ==========
# This list holds all our tasks. It's just a Python list, so data disappears when the server restarts.
tasks = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]

# We track the next available ID so new tasks don't get duplicate IDs
next_id = 4

# ========== DATA SCHEMAS ==========
# These define what shape incoming JSON data should have (validation)
# BaseModel is from pydantic - it checks the data before our function sees it

# TaskCreate: defines what the client sends when creating a task (only needs title)
class TaskCreate(BaseModel):
    title: str

# TaskUpdate: defines what the client sends when updating a task (can update title and/or done)
# The "= None" means these fields are optional
class TaskUpdate(BaseModel):
    title: str = None  # Optional: if not provided, will be None
    done: bool = None  # Optional: if not provided, will be None

# ========== ROOT & HEALTH ==========
@app.get("/")
def read_root():
    # This tells anyone calling the API what it is and what endpoints exist
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }

@app.get("/health")
def health_check():
    # Real companies use this endpoint to check if the server is alive
    return {"status": "ok"}

# ========== READ ==========
@app.get("/tasks")
def get_all_tasks():
    # Return the entire tasks list as JSON
    return tasks

@app.get("/tasks/{id}")
def get_task(id: int):
    # {id} is a path parameter - it gets extracted from the URL
    # Loop through tasks and find one with matching id
    for task in tasks:
        if task["id"] == id:
            # Found it, return just this task
            return task
    
    # If we get here, no task was found, so return 404 error
    raise HTTPException(status_code=404, detail={"error": f"Task {id} not found"})

# ========== CREATE ==========
@app.post("/tasks")
def create_task(task_input: TaskCreate):
    # FastAPI automatically parses the JSON body and validates it using TaskCreate schema
    global next_id  # We need to access and modify the next_id variable
    
    # VALIDATION: Check that title exists and isn't just empty spaces
    if not task_input.title or not task_input.title.strip():
        # .strip() removes leading/trailing spaces. If title is empty after stripping, reject it
        raise HTTPException(status_code=400, detail={"error": "title cannot be empty"})
    
    # Build the new task object with the next available ID
    new_task = {
        "id": next_id,
        "title": task_input.title,
        "done": False  # New tasks always start as not done
    }
    
    # Add it to our tasks list
    tasks.append(new_task)
    
    # Increment next_id so the next task gets a different ID
    next_id += 1
    
    # Return the created task with status 201 (FastAPI does this automatically for POST)
    return new_task

# ========== UPDATE ==========
@app.put("/tasks/{id}")
def update_task(id: int, task_input: TaskUpdate):
    # Loop through tasks looking for the one with matching id
    for task in tasks:
        if task["id"] == id:
            # Found it. Now update the fields that were provided
            
            # Check if title was provided (not None) and update it
            if task_input.title is not None:
                # VALIDATION: title must not be empty
                if not task_input.title.strip():
                    raise HTTPException(status_code=400, detail={"error": "title cannot be empty"})
                # Update the title
                task["title"] = task_input.title
            
            # Check if done status was provided (not None) and update it
            if task_input.done is not None:
                task["done"] = task_input.done
            
            # Return the updated task
            return task
    
    # If we get here, the task ID wasn't found
    raise HTTPException(status_code=404, detail={"error": f"Task {id} not found"})

# ========== DELETE ==========
@app.delete("/tasks/{id}")
def delete_task(id: int):
    # Loop through tasks with enumerate so we get both the index and the task
    for i, task in enumerate(tasks):
        if task["id"] == id:
            # Found it. Remove it from the list using the index
            tasks.pop(i)
            # Return None (FastAPI converts this to 204 No Content status)
            return None
    
    # If we get here, task ID wasn't found
    raise HTTPException(status_code=404, detail={"error": f"Task {id} not found"})