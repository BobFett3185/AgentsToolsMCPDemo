const API_BASE_URL = window.location.origin.startsWith("http")
  ? window.location.origin
  : "http://localhost:8000";

const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const messages = document.querySelector("#messages");
const studentId = document.querySelector("#studentId");

/*
This file handles the frontend for our chat interface. 
No need to code anything in here -- but feel free to mess around with it later on

^ The same goes for index.html and styles.css

*/

function addMessage(role, text) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(message) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      student_id: studentId.value,
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  return response.json();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = input.value.trim();
  if (!message) {
    return;
  }

  addMessage("user", message);
  input.value = "";
  form.querySelector("button").disabled = true;

  try {
    const data = await sendMessage(message);
    addMessage("assistant", data.reply);
  } catch (error) {
    addMessage("assistant", "The API is not reachable yet. Start FastAPI with uvicorn backend.main:app --reload.");
  } finally {
    form.querySelector("button").disabled = false;
    input.focus();
  }
});
