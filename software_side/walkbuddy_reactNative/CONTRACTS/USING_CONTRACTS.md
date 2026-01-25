# **How to Use These Contracts**

These contracts explain **what each part of the system sends** and **what each part receives**.  
They keep the entire project consistent so that everyone can work without breaking each other’s code.

Think of them as **rules for how our code talks to other code**.

---

# **1. Frontend (React Native)**

The React Native app should:

- Capture a camera frame  
- Send it to the `InferenceClient`  
- Display the results returned  
- Never guess what data looks like — always follow the contract  

### What you do:
```ts
inferenceClient.detectVision(frame)
inferenceClient.readText(frame)
```

### What you get back:
- A list of detections  
- Or a list of text blocks  
- Always in the same shape every time  

If you need to draw boxes, convert `bbox_norm` into screen coordinates.

---

# **2. InferenceClient (Frontend Logic)**

This layer hides how inference actually works.

It can:
- Send frames to the backend  
- Or use on-device models in the future  

No matter how it works inside, it must always return **the same result format**.

### Your job:
- Call the backend using the correct route  
- Build the right JSON objects  
- Return results exactly as the contract shows  

The UI depends on these types being correct every time.

---

# **3. Backend (FastAPI)**

The backend receives frames and returns detection/ocr results.

### Your job:
- Accept the incoming image  
- Pass it to the right adapter  
- Return the same JSON format as defined in the contract  
- Use the contract's error format if something goes wrong  

### Very important:

**Do not rename fields.  
Do not remove fields.  
Do not add fields.**

The frontend expects the response to match the contract exactly.

---

# **4. ML Adapters**

Adapters turn model outputs into the contract format.

### Your job:
- Load the YOLO or OCR model  
- Run prediction  
- Convert the raw model results into the JSON shape from the contract  
- Never return raw model data  

Adapters must follow the structure exactly.

---

# **5. Why These Contracts Matter**

These contracts:

- Keep the system stable  
- Make it easy for multiple people to work at once  
- Prevent data shape mismatches  
- Make debugging easier  
- Make future features simple to add  

If everyone follows the same rules, everything works smoothly.

---

# **6. If Something Breaks**

Before debugging, always check:

1. Did the data shape change?  
2. Did someone rename a field?  
3. Did someone add or remove something from the JSON?  
4. Did the wrong format get returned?  

In almost every case, broken behavior comes from breaking the contract.

---

# **7. Simple Final Rule**

**If you return data, make it look exactly like the contract.  
If you receive data, expect it to look exactly like the contract.**

This keeps the whole system reliable.
