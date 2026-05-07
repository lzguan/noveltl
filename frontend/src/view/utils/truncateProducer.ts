function truncateProducer(maxLength : number) : (t : string) => {truncated : string, canTruncate : boolean} {
    function truncateParagraph(t : string) : {truncated : string, canTruncate : boolean} {
        const paragraphs = t.split(/\r?\n/);
        if (paragraphs.length === 0) {
            return { truncated: "", canTruncate: false }
        }
        if (paragraphs.length === 1) {
            const truncated = paragraphs[0].length > maxLength ? paragraphs[0].slice(0, maxLength).concat("...") : paragraphs[0];
            return { truncated, canTruncate: paragraphs[0].length > maxLength }
        }
        const truncated = paragraphs[0].length > maxLength ? paragraphs[0].slice(0, maxLength).concat("...") : paragraphs[0].concat("...");
        return { truncated, canTruncate: true }
    }
    return truncateParagraph
}

export {
    truncateProducer
}