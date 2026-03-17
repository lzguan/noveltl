import React from "react";

type ChapterTextViewerProps = {
    text: string | null;
    loading: boolean;
};

export const ChapterTextViewer: React.FC<ChapterTextViewerProps> = ({ text, loading }) => {
    if (loading) {
        return <div style={{ padding: "20px", color: "#888" }}>Loading...</div>;
    }

    if (text === null) {
        return (
            <div style={{ padding: "20px", color: "#999", fontStyle: "italic" }}>
                Select a chapter and revision to view text.
            </div>
        );
    }

    return (
        <div style={{
            flex: 1,
            overflow: "auto",
            padding: "20px",
            whiteSpace: "pre-wrap",
            fontFamily: "serif",
            fontSize: "1.05rem",
            lineHeight: 1.8,
        }}>
            {text}
        </div>
    );
};
