import { useRef, useEffect, useState } from "react";
import { Worker, Viewer } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import { searchPlugin } from "@react-pdf-viewer/search";

// Import required CSS
import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";
import "@react-pdf-viewer/search/lib/styles/index.css";

interface DocumentPreviewProps {
    fileUrl: string;
    highlightKeyword?: string;
}

export default function DocumentPreview({
    fileUrl,
    highlightKeyword,
}: DocumentPreviewProps) {
    console.log("🎬 DocumentPreview RENDER - fileUrl:", fileUrl, "highlightKeyword:", highlightKeyword);

    // Track the last highlighted keyword to prevent infinite loops
    const lastHighlightedKeyword = useRef<string>("");
    // Track if document is loaded
    const [isDocumentLoaded, setIsDocumentLoaded] = useState(false);

    // Create plugin instances at top level (they call hooks internally)
    const defaultLayoutPluginInstance = defaultLayoutPlugin();
    const searchPluginInstance = searchPlugin();

    // Extract the highlight method
    const { highlight } = searchPluginInstance;

    // Reset document loaded state when fileUrl changes
    useEffect(() => {
        setIsDocumentLoaded(false);
        lastHighlightedKeyword.current = "";
    }, [fileUrl]);

    // Trigger highlighting when keyword changes AND document is loaded
    useEffect(() => {
        console.log("🔍 DocumentPreview - highlightKeyword:", highlightKeyword);
        console.log("🔍 Last highlighted:", lastHighlightedKeyword.current);
        console.log("📄 Document loaded:", isDocumentLoaded);

        // Only highlight if the keyword has actually changed AND document is loaded
        if (
            isDocumentLoaded &&
            highlightKeyword &&
            highlightKeyword.trim() &&
            highlightKeyword !== lastHighlightedKeyword.current
        ) {
            console.log("✅ Calling highlight() with keyword:", highlightKeyword);
            lastHighlightedKeyword.current = highlightKeyword;

            // Small delay to ensure the document is fully rendered
            setTimeout(() => {
                highlight([
                    {
                        keyword: highlightKeyword,
                        matchCase: false,
                    },
                ]);
            }, 300);
        } else {
            console.log("❌ Not highlighting - condition not met");
        }
        // ONLY depend on highlightKeyword and isDocumentLoaded
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [highlightKeyword, isDocumentLoaded]);

    return (
        <div className="h-full w-full">
            <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js">
                <Viewer
                    fileUrl={fileUrl}
                    plugins={[defaultLayoutPluginInstance, searchPluginInstance]}
                    onDocumentLoad={() => {
                        console.log("📗 PDF Document loaded!");
                        setIsDocumentLoaded(true);
                    }}
                />
            </Worker>
        </div>
    );
}
