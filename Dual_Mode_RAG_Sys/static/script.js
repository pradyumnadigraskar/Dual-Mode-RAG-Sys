let isCloud = false;

// 1. Run Health Check & Status UI
window.onload = function() {
    checkHealth(); 
    setInterval(checkHealth, 5000); 
    updateModeUI();
};

async function checkHealth() {
    try {
        const response = await fetch("/health");
        const data = await response.json();
        updateStatusLight("localStatus", data.local);
        updateStatusLight("cloudStatus", data.cloud);
    } catch (error) {
        updateStatusLight("localStatus", false);
        updateStatusLight("cloudStatus", false);
    }
}

function updateStatusLight(elementId, isActive) {
    const el = document.getElementById(elementId);
    if (isActive) {
        el.classList.add("active");
        el.classList.remove("offline");
    } else {
        el.classList.remove("active");
        el.classList.add("offline");
    }
}

// 2. Chat & Upload Logic
document.getElementById("pdfFile").addEventListener("change", function(e) {
    const fileName = e.target.files[0]?.name || "Choose File";
    document.getElementById("fileName").innerText = fileName;
});

function toggleMode() {
    const toggle = document.getElementById("modelToggle");
    isCloud = toggle.checked;
    updateModeUI();
}

function updateModeUI() {
    const desc = document.getElementById("modeDescription");
    if (isCloud) {
        desc.innerHTML = "Using <strong>Gemini 1.5 Flash</strong> for speed & reasoning.";
    } else {
        desc.innerHTML = "Using <strong>Ollama (Mistral)</strong> for local privacy.";
    }
}

async function uploadPDF() {
    const fileInput = document.getElementById("pdfFile");
    const status = document.getElementById("uploadStatus");
    const btn = document.getElementById("uploadBtn");

    if (fileInput.files.length === 0) {
        alert("Please select a PDF file first.");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    status.innerText = "Processing...";
    status.style.color = "#4F46E5";
    btn.disabled = true;

    try {
        const response = await fetch("/upload", { method: "POST", body: formData });
        const data = await response.json();
        
        if (response.ok) {
            status.innerHTML = `<i class="fa-solid fa-check-circle"></i> ${data.details}`;
            status.style.color = "var(--green)";
            addMessage("System", `PDF "${data.filename}" ready!`);
        } else {
            throw new Error(data.detail || "Upload failed");
        }
    } catch (error) {
        status.innerText = "Error: " + error.message;
        status.style.color = "var(--red)";
    } finally {
        btn.disabled = false;
    }
}

// --- FIXED CHAT LOGIC ---
// static/script.js (Partial Update)

async function sendQuery() {
    const queryInput = document.getElementById("userQuery");
    const sendBtn = document.querySelector(".btn-send");
    const query = queryInput.value.trim();
    
    if (!query) return;

    // 1. Add User Message
    addMessage("User", query);
    queryInput.value = ""; 
    
    // Disable inputs
    queryInput.disabled = true;
    sendBtn.disabled = true;

    // 2. Add "Thinking..." Bubble and save its ID
    const thinkingId = "thinking-" + Date.now(); // specialized ID
    addMessage("Bot", '<i class="fa-solid fa-circle-notch fa-spin"></i> Thinking...', thinkingId);

    const mode = isCloud ? "cloud" : "local";
    const formData = new FormData();
    formData.append("query", query);
    formData.append("model_type", mode);

    try {
        const response = await fetch("/chat", { method: "POST", body: formData });
        const data = await response.json();
        
        // 3. Replace "Thinking" with Answer
        replaceThinkingWithAnswer(thinkingId, data.answer);
        
    } catch (error) {
        replaceThinkingWithAnswer(thinkingId, "⚠️ Error: " + error.message);
    } finally {
        // Re-enable inputs
        queryInput.disabled = false;
        sendBtn.disabled = false;
        queryInput.focus();
    }
}

// Update addMessage to accept a custom ID
function addMessage(sender, text, customId = null) {
    const history = document.getElementById("chatHistory");
    const msgDiv = document.createElement("div");
    const isUser = sender === "User";
    
    msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    // Use custom ID if provided, otherwise generate one
    msgDiv.id = customId || ("msg-" + Date.now());
    
    msgDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid ${isUser ? 'fa-user' : 'fa-robot'}"></i></div>
        <div class="bubble">${text}</div>
    `;
    
    history.appendChild(msgDiv);
    history.scrollTop = history.scrollHeight;
    return msgDiv.id;
}

// NEW ROBUST FUNCTION
function replaceThinkingWithAnswer(thinkingId, answerText) {
    const thinkingMsg = document.getElementById(thinkingId);
    
    if (thinkingMsg) {
        // Option A: Update the existing bubble (Smoother)
        const bubble = thinkingMsg.querySelector(".bubble");
        bubble.innerHTML = answerText; 
        
        // If it was the thinking bubble, we might want to change the ID so it doesn't look like "thinking" anymore
        thinkingMsg.id = "msg-" + Date.now();
    } else {
        // Option B: If ID not found (Fallback), just add a new message
        addMessage("Bot", answerText);
    }
}

// --- NEW FUNCTION: Update existing message ---
function updateMessage(id, newText) {
    const msgDiv = document.getElementById(id);
    if (msgDiv) {
        // Find the bubble inside the message div and update text
        const bubble = msgDiv.querySelector(".bubble");
        if (bubble) {
            bubble.innerHTML = newText;
        }
    }
}

document.getElementById("userQuery").addEventListener("keypress", function(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendQuery();
    }
});