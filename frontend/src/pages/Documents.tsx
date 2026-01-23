import { useState, useEffect } from "react";
import { endpoints } from "../config";

interface Document {
  id: number;
  title: string;
  file: string;
  uploaded_at: string;
  is_processed: boolean;
}

export default function Documents() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    const token = localStorage.getItem("token");
    try {
      const response = await fetch(endpoints.documents, {
        headers: {
          Authorization: `Token ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setDocuments(data);
      }
    } catch (error) {
      console.error("Error fetching documents:", error);
    }
  };

  const handleProcess = async (docId: number) => {
    setProcessingId(docId);
    const token = localStorage.getItem("token");
    try {
      const response = await fetch(`${endpoints.documents}${docId}/process/`, {
        method: "POST",
        headers: {
          Authorization: `Token ${token}`,
        },
      });

      if (response.ok) {
        fetchDocuments();
      } else {
        alert("Processing failed");
      }
    } catch (error) {
      console.error("Error processing document:", error);
    } finally {
      setProcessingId(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) return;

    setUploading(true);
    const token = localStorage.getItem("token");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);

    try {
      const response = await fetch(endpoints.documents, {
        method: "POST",
        headers: {
          Authorization: `Token ${token}`,
        },
        body: formData,
      });

      if (response.ok) {
        setTitle("");
        setFile(null);
        // Reset file input
        const fileInput = document.getElementById(
          "file-upload",
        ) as HTMLInputElement;
        if (fileInput) fileInput.value = "";

        fetchDocuments();
      } else {
        alert("Upload failed");
      }
    } catch (error) {
      console.error("Error uploading:", error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 h-full overflow-y-auto">
      <h1 className="text-3xl font-bold mb-8">Documents</h1>

      {/* Upload Section */}
      <div className="mb-12 p-6 border border-black bg-gray-50">
        <h2 className="text-xl font-bold mb-4">Upload New Document</h2>
        <form
          onSubmit={handleUpload}
          className="flex gap-4 items-end flex-wrap"
        >
          <div className="flex-1 min-w-50">
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full p-2 border border-black"
              required
            />
          </div>
          <div className="flex-1 min-w-50">
            <label className="block text-sm font-medium mb-1">File</label>
            <input
              id="file-upload"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full p-2 border border-black bg-white"
              required
            />
          </div>
          <button
            type="submit"
            disabled={uploading}
            className="px-6 py-2 bg-black text-white hover:bg-gray-800 disabled:bg-gray-400"
          >
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </form>
      </div>

      {/* List Section */}
      <div className="grid gap-4">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="p-4 border border-gray-300 flex justify-between items-center bg-white hover:shadow-md transition-shadow"
          >
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg">{doc.title}</h3>
                <span
                  className={`text-xs px-2 py-1 rounded ${doc.is_processed ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}`}
                >
                  {doc.is_processed ? "Processed" : "Unprocessed"}
                </span>
              </div>
              <p className="text-sm text-gray-500">
                Uploaded: {new Date(doc.uploaded_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {!doc.is_processed && (
                <button
                  onClick={() => handleProcess(doc.id)}
                  disabled={processingId === doc.id}
                  className="text-sm px-3 py-1 bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-400"
                >
                  {processingId === doc.id ? "Processing..." : "Process Again"}
                </button>
              )}
              <a
                href={doc.file}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Download
              </a>
            </div>
          </div>
        ))}
        {documents.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            No documents uploaded yet.
          </div>
        )}
      </div>
    </div>
  );
}
