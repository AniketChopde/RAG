// import { useState, useEffect, useRef } from "react"
// import axios from "axios"
// import "tailwindcss/tailwind.css"

// function App() {
//   const [query, setQuery] = useState("")
//   const [chatHistory, setChatHistory] = useState([])
//   const [uploadedDocs, setUploadedDocs] = useState([]) // Track multiple docs
//   const [isLoading, setIsLoading] = useState(false)
//   const [uploadStatus, setUploadStatus] = useState("")
//   const [showDocs, setShowDocs] = useState(false) // For viewing documents
//   const messagesEndRef = useRef(null)

//   useEffect(() => {
//     messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
//   }, [chatHistory])

//   const handleSend = async () => {
//     if (!query.trim() || isLoading) return

//     setIsLoading(true)
//     try {
//       const formData = new FormData()
//       formData.append("query", query)

//       const res = await axios.post("http://localhost:8000/chat/text", formData)
//       setChatHistory(res.data.chat_history)
//       setQuery("")
//     } catch (err) {
//       console.error(err)
//       setUploadStatus("Error sending message")
//       setTimeout(() => setUploadStatus(""), 3000)
//     } finally {
//       setIsLoading(false)
//     }
//   }

//   const handleUpload = async (e) => {
//     const file = e.target.files[0]
//     if (!file) return

//     const allowedTypes = [
//       "application/pdf",
//       "text/plain",
//       "application/msword",
//       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
//     ]
//     if (!allowedTypes.includes(file.type)) {
//       setUploadStatus("Please upload a PDF, DOC, DOCX, or TXT file")
//       setTimeout(() => setUploadStatus(""), 3000)
//       return
//     }

//     const formData = new FormData()
//     formData.append("file", file)

//     setUploadStatus("Uploading document...")
//     try {
//       const res = await axios.post("http://localhost:8000/upload_document", formData)
//       setUploadStatus(`Document uploaded successfully: ${file.name}`)
//       setUploadedDocs((prev) => [...prev, { id: res.data.document_id, name: file.name }]) // store filename too
//       setTimeout(() => setUploadStatus(""), 3000)
//     } catch (err) {
//       console.error(err)
//       setUploadStatus("Upload failed. Please try again.")
//       setTimeout(() => setUploadStatus(""), 3000)
//     }
//   }

//   const handleRemove = async () => {
//     if (uploadedDocs.length === 0) {
//       setUploadStatus("No document to remove")
//       setTimeout(() => setUploadStatus(""), 3000)
//       return
//     }

//     // Remove last uploaded document
//     const docToRemove = uploadedDocs[uploadedDocs.length - 1]

//     try {
//       const formData = new FormData()
//       formData.append("document_id", docToRemove.id)

//       await axios.post("http://localhost:8000/remove_document", formData)
//       setUploadStatus("Document removed successfully")
//       setUploadedDocs((prev) => prev.filter((doc) => doc.id !== docToRemove.id))
//       setTimeout(() => setUploadStatus(""), 3000)
//     } catch (err) {
//       console.error(err)
//       setUploadStatus("Failed to remove document")
//       setTimeout(() => setUploadStatus(""), 3000)
//     }
//   }

//   const handleKeyPress = (e) => {
//     if (e.key === "Enter" && !e.shiftKey) {
//       e.preventDefault()
//       handleSend()
//     }
//   }

//   return (
//     <div className="flex flex-col h-screen bg-slate-50">
//       {/* Header */}
//       <header className="bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg border-b border-emerald-700">
//         <div className="max-w-6xl mx-auto px-6 py-4">
//           <div className="flex justify-between items-center">
//             <div className="flex items-center gap-3">
//               <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
//                 <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                   <path
//                     strokeLinecap="round"
//                     strokeLinejoin="round"
//                     strokeWidth={2}
//                     d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
//                   />
//                 </svg>
//               </div>
//               <div>
//                 <h1 className="text-xl font-bold">AI Document Assistant</h1>
//                 <p className="text-emerald-100 text-sm">Powered by RAG technology</p>
//               </div>
//             </div>
//             {uploadedDocs.length > 0 && (
//               <div className="flex items-center gap-2 bg-white/20 px-3 py-2 rounded-lg backdrop-blur-sm">
//                 <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
//                 <span className="text-sm font-medium">
//                   {uploadedDocs.length} document{uploadedDocs.length > 1 ? "s" : ""} loaded
//                 </span>
//               </div>
//             )}
//           </div>
//         </div>
//       </header>

//       {/* Main Chat Area */}
//       <main className="flex-1 overflow-y-auto bg-slate-50">
//         <div className="max-w-4xl mx-auto px-6 py-6">
//           {chatHistory.length === 0 ? (
//             <div className="flex flex-col items-center justify-center h-full text-center py-20">
//               <div className="w-20 h-20 bg-gradient-to-br from-emerald-100 to-teal-100 rounded-2xl flex items-center justify-center mb-6">
//                 <svg className="w-10 h-10 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                   <path
//                     strokeLinecap="round"
//                     strokeLinejoin="round"
//                     strokeWidth={2}
//                     d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
//                   />
//                 </svg>
//               </div>
//               <h2 className="text-2xl font-bold text-slate-800 mb-3">Start a conversation</h2>
//               <p className="text-slate-600 max-w-md leading-relaxed">
//                 Upload documents and ask questions about them, or just start chatting with the AI assistant!
//               </p>
//             </div>
//           ) : (
//             <div className="space-y-6">
//               {chatHistory.map((msg, idx) => (
//                 <div key={idx} className="space-y-4">
//                   {/* User Message */}
//                   <div className="flex justify-end">
//                     <div className="flex items-start gap-3 max-w-2xl">
//                       <div className="bg-emerald-600 text-white p-4 rounded-2xl rounded-br-md shadow-lg">
//                         <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.user}</p>
//                       </div>
//                       <div className="w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center flex-shrink-0">
//                         <svg className="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                           <path
//                             strokeLinecap="round"
//                             strokeLinejoin="round"
//                             strokeWidth={2}
//                             d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 13l-3-3m0 0l-3 3m3-3v12"
//                           />
//                         </svg>
//                       </div>
//                     </div>
//                   </div>

//                   {/* Assistant Message */}
//                   <div className="flex justify-start">
//                     <div className="flex items-start gap-3 max-w-2xl">
//                       <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full flex items-center justify-center flex-shrink-0">
//                         <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                           <path
//                             strokeLinecap="round"
//                             strokeLinejoin="round"
//                             strokeWidth={2}
//                             d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
//                           />
//                         </svg>
//                       </div>
//                       <div className="bg-white border border-slate-200 p-4 rounded-2xl rounded-bl-md shadow-sm">
//                         <p className="text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">{msg.assistant}</p>
//                       </div>
//                     </div>
//                   </div>
//                 </div>
//               ))}

//               {isLoading && (
//                 <div className="flex justify-start">
//                   <div className="flex items-start gap-3 max-w-2xl">
//                     <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full flex items-center justify-center flex-shrink-0">
//                       <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                         <path
//                           strokeLinecap="round"
//                           strokeLinejoin="round"
//                           strokeWidth={2}
//                           d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
//                         />
//                       </svg>
//                     </div>
//                     <div className="bg-white border border-slate-200 p-4 rounded-2xl rounded-bl-md shadow-sm">
//                       <div className="flex gap-1">
//                         <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
//                         <div
//                           className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
//                           style={{ animationDelay: "0.1s" }}
//                         ></div>
//                         <div
//                           className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
//                           style={{ animationDelay: "0.2s" }}
//                         ></div>
//                       </div>
//                     </div>
//                   </div>
//                 </div>
//               )}
//             </div>
//           )}
//           <div ref={messagesEndRef} />
//         </div>
//       </main>

//       {/* Input Area */}
//       <footer className="bg-white border-t border-slate-200 shadow-lg">
//         <div className="max-w-4xl mx-auto p-6">
//           {/* Status Message */}
//           {uploadStatus && (
//             <div
//               className={`mb-4 p-3 rounded-lg text-sm font-medium text-center ${
//                 uploadStatus.includes("Error") || uploadStatus.includes("failed")
//                   ? "bg-red-50 text-red-700 border border-red-200"
//                   : "bg-green-50 text-green-700 border border-green-200"
//               }`}
//             >
//               <div className="flex items-center justify-center gap-2">
//                 {uploadStatus.includes("Error") || uploadStatus.includes("failed") ? (
//                   <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                     <path
//                       strokeLinecap="round"
//                       strokeLinejoin="round"
//                       strokeWidth={2}
//                       d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
//                     />
//                   </svg>
//                 ) : (
//                   <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                     <path
//                       strokeLinecap="round"
//                       strokeLinejoin="round"
//                       strokeWidth={2}
//                       d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
//                     />
//                   </svg>
//                 )}
//                 {uploadStatus}
//               </div>
//             </div>
//           )}

//           {/* Input Wrapper */}
//           <div className="flex items-end gap-3 mb-4">
//             <div className="flex-1 relative">
//               <textarea
//                 value={query}
//                 onChange={(e) => setQuery(e.target.value)}
//                 onKeyPress={handleKeyPress}
//                 placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
//                 className="w-full min-h-[60px] max-h-32 p-4 pr-12 border-2 border-slate-200 rounded-xl bg-white text-slate-700 placeholder-slate-400 resize-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 focus:outline-none transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
//                 disabled={isLoading}
//                 rows={1}
//               />
//               <button
//                 onClick={() => document.getElementById("file-input").click()}
//                 className="absolute right-3 bottom-3 p-2 text-slate-400 hover:text-emerald-600 transition-colors duration-200"
//                 disabled={isLoading}
//               >
//                 <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                   <path
//                     strokeLinecap="round"
//                     strokeLinejoin="round"
//                     strokeWidth={2}
//                     d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
//                   />
//                 </svg>
//               </button>
//             </div>
//             <button
//               onClick={handleSend}
//               disabled={!query.trim() || isLoading}
//               className="w-12 h-12 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white rounded-xl flex items-center justify-center transition-all duration-200 transform hover:scale-105 disabled:transform-none shadow-lg"
//             >
//               {isLoading ? (
//                 <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
//               ) : (
//                 <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                   <path
//                     strokeLinecap="round"
//                     strokeLinejoin="round"
//                     strokeWidth={2}
//                     d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
//                   />
//                 </svg>
//               )}
//             </button>
//           </div>

//           {/* Action Buttons */}
//           <div className="flex items-center justify-center gap-3 flex-wrap">
//             <label className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg cursor-pointer transition-colors duration-200 border border-slate-200">
//               <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                 <path
//                   strokeLinecap="round"
//                   strokeLinejoin="round"
//                   strokeWidth={2}
//                   d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
//                 />
//               </svg>
//               <span className="text-sm font-medium">Upload Document</span>
//               <input
//                 id="file-input"
//                 type="file"
//                 onChange={handleUpload}
//                 accept=".pdf,.doc,.docx,.txt"
//                 className="hidden"
//               />
//             </label>

//             {uploadedDocs.length > 0 && (
//               <>
//                 <button
//                   onClick={handleRemove}
//                   className="flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-700 rounded-lg transition-colors duration-200 border border-red-200"
//                 >
//                   <span className="text-sm font-medium">Remove Document</span>
//                 </button>

//                 <button
//                   onClick={() => setShowDocs(true)}
//                   className="flex items-center gap-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors duration-200 border border-blue-200"
//                 >
//                   <span className="text-sm font-medium">View Documents</span>
//                 </button>
//               </>
//             )}
//           </div>
//         </div>
//       </footer>

//       {/* Uploaded Documents Modal */}
//       {showDocs && (
//         <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
//           <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-lg">
//             <h2 className="text-lg font-bold mb-4">Uploaded Documents</h2>
//             <ul className="space-y-2 max-h-60 overflow-y-auto">
//               {uploadedDocs.map((doc, idx) => (
//                 <li key={idx} className="border-b border-slate-200 py-2 text-sm text-slate-700">
//                   {doc.name} (ID: {doc.id})
//                 </li>
//               ))}
//             </ul>
//             <div className="mt-4 text-right">
//               <button
//                 onClick={() => setShowDocs(false)}
//                 className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg"
//               >
//                 Close
//               </button>
//             </div>
//           </div>
//         </div>
//       )}
//     </div>
//   )
// }

// export default App
