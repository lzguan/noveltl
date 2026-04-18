import { Card, CardTitle, CardContent, CardHeader, CardDescription } from "@/components/ui/card"
import { ExpandableText } from "@/components/text/ExpandableText"
import { type Novel } from "@/types/novel";
import { routeTo } from "@/routes";

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

const truncate = truncateProducer(1000)

function NovelCard({ novel, showDescription=false }: { novel: Novel, showDescription? : boolean }) {
    return <Card className="text-left">
        <>
            <CardHeader>
                <CardTitle>{<a href={routeTo.view.novel(novel.novelId)}>{novel.novelTitle}</a>}</CardTitle>
                <CardDescription>
                    <div style={{ fontStyle: novel.novelAuthor ? "normal" : "italic" }}>
                        {novel.novelAuthor || "Unknown Author"}
                    </div>
                </CardDescription>
            </CardHeader>
            {
                showDescription &&
                <CardContent>
                    <div style={{ fontStyle: novel.novelDescription ? "normal" : "italic" }}>
                        <ExpandableText text={novel.novelDescription || "No description available."} truncate={truncate} />
                    </div>
                </CardContent>
            }
            
        </>
    </Card>
}

export {
    truncateProducer,
    NovelCard
}
