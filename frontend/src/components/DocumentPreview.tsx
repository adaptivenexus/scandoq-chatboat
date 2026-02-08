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


    // Track the last highlighted keyword to prevent infinite loops
    const lastHighlightedKeyword = useRef<string>("");
    // Track if document is loaded
    const [isDocumentLoaded, setIsDocumentLoaded] = useState(false);

    // Create plugin instances at top level (they call hooks internally)
    const defaultLayoutPluginInstance = defaultLayoutPlugin();
    const searchPluginInstance = searchPlugin();

    // Extract the highlight method
    const { highlight } = searchPluginInstance;

    // Ref for the container to check for highlight elements
    const containerRef = useRef<HTMLDivElement>(null);

    // Reset document loaded state when fileUrl changes
    useEffect(() => {
        setIsDocumentLoaded(false);
        lastHighlightedKeyword.current = "";
    }, [fileUrl]);

    // Trigger highlighting when keyword changes AND document is loaded
    useEffect(() => {


        // Only highlight if the keyword has actually changed AND document is loaded
        if (
            isDocumentLoaded &&
            highlightKeyword &&
            highlightKeyword.trim() &&
            highlightKeyword !== lastHighlightedKeyword.current
        ) {

            lastHighlightedKeyword.current = highlightKeyword;

            // STRATEGY: Try Exact Phrase -> Fallback to Split Words
            // 1. Try highlighting the exact phrase first
            setTimeout(() => {
                highlight([{
                    keyword: highlightKeyword,
                    matchCase: false,
                }]);

                // 2. Check if any highlights were created after a short render delay
                setTimeout(() => {
                    const hasMatches = containerRef.current?.querySelectorAll('.rpv-search__highlight').length &&
                        containerRef.current?.querySelectorAll('.rpv-search__highlight').length > 0;

                    if (!hasMatches) {
                        // Split the keyword string into individual words to handle non-contiguous matches
                        // This is important for tables where "Website Development" and "Cost" might be far apart
                        const keywords = highlightKeyword.split(/\s+/).filter(k => k.length > 1);

                        // Create highlight parameters for each individual word
                        const highlightParams = keywords.map(k => ({
                            keyword: k,
                            matchCase: false,
                        }));

                        highlight(highlightParams);
                    }
                }, 500); // Wait for exact match render
            }, 300); // Wait for document ready
        }
        // ONLY depend on highlightKeyword and isDocumentLoaded
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [highlightKeyword, isDocumentLoaded]);

    return (
        <div className="h-full w-full" ref={containerRef}>
            <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js">
                <Viewer
                    fileUrl={fileUrl}
                    plugins={[defaultLayoutPluginInstance, searchPluginInstance]}
                    onDocumentLoad={() => {
                        setIsDocumentLoaded(true);
                    }}
                />
            </Worker>
        </div>
    );
}
