import { useState, useEffect, useRef } from "react"
import axios from "axios"
import "tailwindcss/tailwind.css"

function App() {
  const [query, setQuery] = useState("")
  const [chatHistory, setChatHistory] = useState([])
  const [uploadedDocs, setUploadedDocs] = useState([]) // Track multiple docs
  const [isLoading, setIsLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState("")
  const [showDocs, setShowDocs] = useState(false) // For viewing documents
  const messagesEndRef = useRef(null)
  const [conversationId, setConversationId] = useState("")
  const [token, setToken] = useState(localStorage.getItem("auth_token") || "")
  const [authMode, setAuthMode] = useState("login") // 'login' | 'register'
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [adminTokenForRegister, setAdminTokenForRegister] = useState("")
  const [me, setMe] = useState(null)
  const [showUserStats, setShowUserStats] = useState(false) // For viewing user statistics

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatHistory])

  // Initialize or load conversationId, then load history and documents
  useEffect(() => {
    let cid = localStorage.getItem("conversation_id")
    if (!cid) {
      cid = crypto.randomUUID()
      localStorage.setItem("conversation_id", cid)
    }
    setConversationId(cid)

    const loadState = async () => {
      try {
        const [hRes, dRes] = await Promise.all([
          axios.get("http://localhost:8000/history", { params: { conversation_id: cid } }),
          axios.get("http://localhost:8000/documents", { params: { conversation_id: cid } }),
        ])
        setChatHistory(hRes.data.chat_history || [])
        setUploadedDocs(dRes.data.documents || [])
      } catch (e) {
        // ignore on first load if not present
      }
    }
    loadState()
  }, [])

  // Keep axios Authorization header in sync
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`
      localStorage.setItem("auth_token", token)
    } else {
      delete axios.defaults.headers.common["Authorization"]
      localStorage.removeItem("auth_token")
    }
  }, [token])

  useEffect(() => {
    const fetchMe = async () => {
      if (!token) { setMe(null); return }
      try {
        const res = await axios.get("http://localhost:8000/me")
        setMe(res.data)
      } catch (_) {
        setMe(null)
      }
    }
    fetchMe()
  }, [token])

  const handleLogin = async (e) => {
    e?.preventDefault()
    if (!username || !password) return
    try {
      const form = new FormData()
      form.append("username", username)
      form.append("password", password)
      const res = await axios.post("http://localhost:8000/auth/login", form)
      setToken(res.data.token)
      setUploadStatus("Logged in")
      setTimeout(() => setUploadStatus(""), 2000)
    } catch (err) {
      setUploadStatus("Login failed")
      setTimeout(() => setUploadStatus(""), 3000)
    }
  }

  const handleLogout = async () => {
    try {
      await axios.post("http://localhost:8000/auth/logout")
    } catch (_) {}
    setToken("")
    setUsername("")
    setPassword("")
  }

  const handleRegisterUser = async (e) => {
    e?.preventDefault()
    if (!username || !password) return
    try {
      const form = new FormData()
      form.append("username", username)
      form.append("password", password)
      await axios.post("http://localhost:8000/auth/register", form)
      setUploadStatus("User registered. You can now login.")
      setTimeout(() => setUploadStatus(""), 3000)
      setAuthMode("login")
    } catch (err) {
      setUploadStatus("Registration failed. Username may already exist.")
      setTimeout(() => setUploadStatus(""), 4000)
    }
  }

  const handleSend = async () => {
    if (!query.trim() || isLoading) return

    setIsLoading(true)
    try {
      const formData = new FormData()
      formData.append("query", query)
      formData.append("conversation_id", conversationId)

      const res = await axios.post("http://localhost:8000/chat/text", formData)
      setChatHistory(res.data.chat_history)
      if (res.data.conversation_id && res.data.conversation_id !== conversationId) {
        localStorage.setItem("conversation_id", res.data.conversation_id)
        setConversationId(res.data.conversation_id)
      }
      setQuery("")
    } catch (err) {
      console.error(err)
      setUploadStatus("Error sending message")
      setTimeout(() => setUploadStatus(""), 3000)
    } finally {
      setIsLoading(false)
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    const allowedTypes = [
      "application/pdf",
      "text/plain",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/csv",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    if (!allowedTypes.includes(file.type)) {
      setUploadStatus("Please upload a PDF, DOCX, TXT, CSV, XLS, or XLSX file")
      setTimeout(() => setUploadStatus(""), 3000)
      return
    }

    const formData = new FormData()
    formData.append("file", file)
    formData.append("conversation_id", conversationId)

    setUploadStatus("Uploading document...")
    try {
      const res = await axios.post("http://localhost:8000/upload_document", formData)
      setUploadStatus(`Document uploaded successfully: ${file.name}`)
      setUploadedDocs((prev) => [...prev, { id: res.data.document_id, name: file.name }]) // store filename too
      setTimeout(() => setUploadStatus(""), 3000)
    } catch (err) {
      console.error(err)
      setUploadStatus("Upload failed. Please try again.")
      setTimeout(() => setUploadStatus(""), 3000)
    }
  }

  const handleRemove = async () => {
    if (uploadedDocs.length === 0) {
      setUploadStatus("No document to remove")
      setTimeout(() => setUploadStatus(""), 3000)
      return
    }

    // Remove last uploaded document
    const docToRemove = uploadedDocs[uploadedDocs.length - 1]

    try {
      const formData = new FormData()
      formData.append("document_id", docToRemove.id)

      await axios.post("http://localhost:8000/remove_document", formData)
      setUploadStatus("Document removed successfully")
      setUploadedDocs((prev) => prev.filter((doc) => doc.id !== docToRemove.id))
      setTimeout(() => setUploadStatus(""), 3000)
    } catch (err) {
      console.error(err)
      setUploadStatus("Failed to remove document")
      setTimeout(() => setUploadStatus(""), 3000)
    }
  }

  const handleRemoveSpecific = async (docId) => {
    try {
      const formData = new FormData()
      formData.append("document_id", docId)
      await axios.post("http://localhost:8000/remove_document", formData)
      setUploadedDocs((prev) => prev.filter((doc) => doc.id !== docId))
    } catch (err) {
      console.error(err)
      setUploadStatus("Failed to remove document")
      setTimeout(() => setUploadStatus(""), 3000)
    }
  }

  const handleClearHistory = async () => {
    if (!conversationId) return
    try {
      const formData = new FormData()
      formData.append("conversation_id", conversationId)
      await axios.post("http://localhost:8000/clear_history", formData)
      setChatHistory([])
    } catch (err) {
      console.error(err)
      setUploadStatus("Failed to clear history")
      setTimeout(() => setUploadStatus(""), 3000)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // If not authenticated, show auth screen
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-lg p-6">
          <div className="flex mb-6">
            <button
              className={`flex-1 py-2 rounded-l-lg border ${authMode === "login" ? "bg-emerald-600 text-white border-emerald-700" : "bg-slate-100 text-slate-700 border-slate-200"}`}
              onClick={() => setAuthMode("login")}
            >
              Login
            </button>
            <button
              className={`flex-1 py-2 rounded-r-lg border ${authMode === "register" ? "bg-emerald-600 text-white border-emerald-700" : "bg-slate-100 text-slate-700 border-slate-200"}`}
              onClick={() => setAuthMode("register")}
            >
              Register (Admin-only)
            </button>
          </div>

          {authMode === "login" ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">Username</label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-200" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-200" />
              </div>
              <button type="submit" className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg">Login</button>
            </form>
          ) : (
            <form onSubmit={handleRegisterUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">New Username</label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-200" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">New Password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-200" />
              </div>
              <button type="submit" className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg">Register User</button>
            </form>
          )}

          {uploadStatus && (
            <div className="mt-4 text-center text-sm text-slate-700">{uploadStatus}</div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg border-b border-emerald-700">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold">AI Document Assistant</h1>
                <p className="text-emerald-100 text-sm">Powered by RAG technology</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {uploadedDocs.length > 0 && (
                <div className="flex items-center gap-2 bg-white/20 px-3 py-2 rounded-lg backdrop-blur-sm">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-sm font-medium">
                    {uploadedDocs.length} document{uploadedDocs.length > 1 ? "s" : ""} loaded
                  </span>
                </div>
              )}
              {me?.role === 'admin' && (
                <span className="px-2 py-1 bg-yellow-400/20 text-yellow-100 border border-yellow-300/40 rounded text-xs">Admin</span>
              )}
              <button onClick={handleLogout} className="px-3 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm">Logout</button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <div className="max-w-4xl mx-auto px-6 py-6">
          {chatHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-20">
              <div className="w-20 h-20 bg-gradient-to-br from-emerald-100 to-teal-100 rounded-2xl flex items-center justify-center mb-6">
                <svg className="w-10 h-10 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-3">Start a conversation</h2>
              <p className="text-slate-600 max-w-md leading-relaxed">
                Upload documents and ask questions about them, or just start chatting with the AI assistant!
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {chatHistory.map((msg, idx) => (
                <div key={idx} className="space-y-4">
                  {/* User Message */}
                  <div className="flex justify-end">
                    <div className="flex items-start gap-3 max-w-2xl">
                      <div className="bg-emerald-600 text-white p-4 rounded-2xl rounded-br-md shadow-lg">
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.user}</p>
                      </div>
                      <div className="w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center flex-shrink-0">
                        <svg className="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 13l-3-3m0 0l-3 3m3-3v12"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* Assistant Message */}
                  <div className="flex justify-start">
                    <div className="flex items-start gap-3 max-w-2xl">
                      <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full flex items-center justify-center flex-shrink-0">
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                          />
                        </svg>
                      </div>
                      <div className="bg-white border border-slate-200 p-4 rounded-2xl rounded-bl-md shadow-sm">
                        <p className="text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">{msg.assistant}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-start gap-3 max-w-2xl">
                    <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full flex items-center justify-center flex-shrink-0">
                      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                        />
                      </svg>
                    </div>
                    <div className="bg-white border border-slate-200 p-4 rounded-2xl rounded-bl-md shadow-sm">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                        <div
                          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                          style={{ animationDelay: "0.1s" }}
                        ></div>
                        <div
                          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                          style={{ animationDelay: "0.2s" }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="bg-white border-t border-slate-200 shadow-lg">
        <div className="max-w-4xl mx-auto p-6">
          {/* Status Message */}
          {uploadStatus && (
            <div
              className={`mb-4 p-3 rounded-lg text-sm font-medium text-center ${
                uploadStatus.includes("Error") || uploadStatus.includes("failed")
                  ? "bg-red-50 text-red-700 border border-red-200"
                  : "bg-green-50 text-green-700 border border-green-200"
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                {uploadStatus.includes("Error") || uploadStatus.includes("failed") ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                )}
                {uploadStatus}
              </div>
            </div>
          )}

          {/* Input Wrapper */}
          <div className="flex items-end gap-3 mb-4">
            <div className="flex-1 relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
                className="w-full min-h-[60px] max-h-32 p-4 pr-12 border-2 border-slate-200 rounded-xl bg-white text-slate-700 placeholder-slate-400 resize-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 focus:outline-none transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
                disabled={isLoading}
                rows={1}
              />
              <button
                onClick={() => document.getElementById("file-input").click()}
                className="absolute right-3 bottom-3 p-2 text-slate-400 hover:text-emerald-600 transition-colors duration-200"
                disabled={isLoading}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                  />
                </svg>
              </button>
            </div>
            <button
              onClick={handleSend}
              disabled={!query.trim() || isLoading}
              className="w-12 h-12 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white rounded-xl flex items-center justify-center transition-all duration-200 transform hover:scale-105 disabled:transform-none shadow-lg"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              )}
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <label className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg cursor-pointer transition-colors duration-200 border border-slate-200">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <span className="text-sm font-medium">Upload Document</span>
              <input
                id="file-input"
                type="file"
                onChange={handleUpload}
                accept=".pdf,.doc,.docx,.txt,.csv,.xls,.xlsx,.pptx,.png,.jpg,.jpeg,.tif,.tiff"
                className="hidden"
              />
            </label>

            {uploadedDocs.length > 0 && (
              <>
                <button
                  onClick={handleRemove}
                  className="flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-700 rounded-lg transition-colors duration-200 border border-red-200"
                >
                  <span className="text-sm font-medium">Remove Document</span>
                </button>

                <button
                  onClick={() => setShowDocs(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors duration-200 border border-blue-200"
                >
                  <span className="text-sm font-medium">View Documents</span>
                </button>
              </>
            )}

            {uploadedDocs.length === 0 && me?.role === 'admin' && (
              <button
                onClick={() => setShowDocs(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors duration-200 border border-blue-200"
              >
                <span className="text-sm font-medium">View Documents</span>
              </button>
            )}

            <button
              onClick={handleClearHistory}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors duration-200 border border-slate-200"
            >
              <span className="text-sm font-medium">Clear Chat</span>
            </button>

            <button
              onClick={() => setShowUserStats(true)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-lg transition-colors duration-200 border border-purple-200"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
              </svg>
              <span className="text-sm font-medium">User Stats</span>
            </button>
          </div>
        </div>
      </footer>

      {/* Uploaded Documents Modal */}
      {showDocs && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-lg">
            <h2 className="text-lg font-bold mb-4">Uploaded Documents</h2>
            <ul className="space-y-2 max-h-60 overflow-y-auto">
              {uploadedDocs.map((doc, idx) => (
                <li key={idx} className="flex items-center justify-between border-b border-slate-200 py-2 text-sm text-slate-700">
                  <span>{doc.name} (ID: {doc.id})</span>
                  <button
                    onClick={() => handleRemoveSpecific(doc.id)}
                    className="px-2 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded"
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
            {me?.role === 'admin' && (
              <AdminBuiltins />
            )}
            <div className="mt-4 text-right">
              <button
                onClick={() => setShowDocs(false)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User Statistics Modal */}
      {showUserStats && (
        <UserStatsModal
          onClose={() => setShowUserStats(false)}
          currentUser={me}
        />
      )}
    </div>
  )
}

function AdminBuiltins() {
  const [builtins, setBuiltins] = useState([])
  const [status, setStatus] = useState("")
  const [folderFiles, setFolderFiles] = useState([])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get("http://localhost:8000/admin/inbuilt-documents")
        setBuiltins(res.data.documents || [])
      } catch (e) {}
      try {
        const fres = await axios.get("http://localhost:8000/admin/documents-folder")
        setFolderFiles(fres.data.files || [])
      } catch (e) {}
    }
    load()
  }, [])

  const removeBuiltin = async (id) => {
    try {
      const form = new FormData()
      form.append("document_id", id)
      await axios.post("http://localhost:8000/remove_document", form)
      setBuiltins(prev => prev.filter(b => b.id !== id))
      setStatus("Removed built-in document")
      setTimeout(() => setStatus(""), 2000)
    } catch (e) {
      setStatus("Failed to remove built-in document")
      setTimeout(() => setStatus(""), 2000)
    }
  }

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between">
        <h3 className="text-md font-semibold">Built-in Documents (Admin)</h3>
        {status && <span className="text-xs text-slate-500">{status}</span>}
      </div>
      <ul className="space-y-2 max-h-60 overflow-y-auto mt-2">
        {builtins.map((doc) => (
          <li key={doc.id} className="flex items-center justify-between border-b border-slate-200 py-2 text-sm text-slate-700">
            <span>{doc.name} (ID: {doc.id})</span>
            <button onClick={() => removeBuiltin(doc.id)} className="px-2 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded">Delete</button>
          </li>
        ))}
        {builtins.length === 0 && (
          <li className="text-sm text-slate-500">No built-in documents found.</li>
        )}
      </ul>

      <div className="mt-6">
        <h3 className="text-md font-semibold">Backend documents folder (Admin)</h3>
        <ul className="space-y-2 max-h-60 overflow-y-auto mt-2">
          {folderFiles.map((f) => (
            <li key={f.name} className="flex items-center justify-between border-b border-slate-200 py-2 text-sm text-slate-700">
              <span>{f.name} {f.size != null ? `(size: ${f.size} bytes)` : ''}</span>
              <button onClick={async () => {
                try {
                  const form = new FormData()
                  form.append('filename', f.name)
                  await axios.post('http://localhost:8000/admin/documents-folder/delete', form)
                  setFolderFiles(prev => prev.filter(x => x.name !== f.name))
                  setStatus('Deleted file and cleaned index')
                  setTimeout(() => setStatus(''), 2000)
                } catch (e) {
                  setStatus('Failed to delete file')
                  setTimeout(() => setStatus(''), 2000)
                }
              }} className="px-2 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded">Delete</button>
            </li>
          ))}
          {folderFiles.length === 0 && (
            <li className="text-sm text-slate-500">No files in backend documents folder.</li>
          )}
        </ul>
      </div>
    </div>
  )
}

function UserStatsModal({ onClose, currentUser }) {
  const [userStats, setUserStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true)
        let endpoint = currentUser?.role === 'admin' ? 'admin/user-stats' : 'users/overview'
        const res = await axios.get(`http://localhost:8000/${endpoint}`)
        setUserStats(res.data)
        setError("")
      } catch (e) {
        setError("Failed to load user statistics")
        console.error("Error loading user stats:", e)
      } finally {
        setLoading(false)
      }
    }
    loadStats()
  }, [currentUser])

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl max-w-4xl w-full p-6 shadow-lg max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">
            User Statistics - All Users
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {userStats && !loading && (
          <>
            {/* Activity Summary */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold mb-4">System Activity Summary</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{userStats.activity_summary.total_users}</div>
                  <div className="text-sm text-blue-800">Total Users</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{userStats.activity_summary.total_admins}</div>
                  <div className="text-sm text-green-800">Admins</div>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">{userStats.activity_summary.total_documents}</div>
                  <div className="text-sm text-purple-800">Total Documents</div>
                </div>
                <div className="bg-orange-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-orange-600">{userStats.activity_summary.recent_uploads_7d}</div>
                  <div className="text-sm text-orange-800">Uploads (7d)</div>
                </div>
              </div>
            </div>

            {/* User Statistics */}
            <div>
              <h3 className="text-lg font-semibold mb-4">
                {currentUser?.role === 'admin' ? 'All Users (Detailed)' : 'All Users (Overview)'}
              </h3>

              {currentUser?.role === 'admin' ? (
                <div className="space-y-4">
                  {userStats.users.map((user, index) => (
                    <div key={index} className="border border-slate-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${user.role === 'admin' ? 'bg-red-500' : 'bg-green-500'}`}></div>
                          <h4 className="font-semibold">{user.username}</h4>
                          <span className={`px-2 py-1 text-xs rounded-full ${
                            user.role === 'admin' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                          }`}>
                            {user.role}
                          </span>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-slate-600">Documents: {user.document_count}</div>
                          {user.last_upload && (
                            <div className="text-xs text-slate-500">
                              Last upload: {new Date(user.last_upload).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      </div>

                      {user.document_names.length > 0 && (
                        <div className="mt-3">
                          <div className="text-sm font-medium text-slate-700 mb-2">Documents:</div>
                          <div className="flex flex-wrap gap-2">
                            {user.document_names.map((docName, docIndex) => (
                              <span key={docIndex} className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded">
                                {docName}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {user.document_names.length === 0 && (
                        <div className="text-sm text-slate-500 mt-2">No documents uploaded</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-4">
                  {userStats.users.map((user, index) => (
                    <div key={index} className="border border-slate-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${user.role === 'admin' ? 'bg-red-500' : 'bg-green-500'}`}></div>
                          <h4 className="font-semibold">{user.username}</h4>
                          <span className={`px-2 py-1 text-xs rounded-full ${
                            user.role === 'admin' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                          }`}>
                            {user.role}
                          </span>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-slate-600">Documents: {user.document_count}</div>
                          {user.joined_date && (
                            <div className="text-xs text-slate-500">
                              Joined: {new Date(user.joined_date).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="text-sm text-slate-500 mt-2">
                        {user.document_count === 0 ? 'No documents uploaded' : `${user.document_count} document${user.document_count !== 1 ? 's' : ''} uploaded`}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        <div className="mt-6 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
