import { Card, CardTitle, CardContent, CardHeader, CardDescription } from "@/components/ui/card";
import { ExpandableText } from "@/components/text/ExpandableText";
import { routeTo } from "@/routes";
import type { Novel } from "@/client";
import { truncateProducer } from "../utils/truncateProducer";
import { Link } from "react-router-dom";

const truncate = truncateProducer(1000);

function NovelCard({
  novel,
  showDescription = false,
}: {
  novel: Novel;
  showDescription?: boolean;
}) {
  return (
    <Card className="text-left">
      <>
        <CardHeader>
          <CardTitle>
            {
              <Link className="hover:underline" to={routeTo.view.novel(novel.novelId)}>
                {novel.novelTitle}
              </Link>
            }
          </CardTitle>
          <CardDescription>
            <div style={{ fontStyle: novel.novelAuthor ? "normal" : "italic" }}>
              {novel.novelAuthor || "Unknown Author"}
            </div>
          </CardDescription>
        </CardHeader>
        {showDescription && (
          <CardContent>
            <div style={{ fontStyle: novel.novelDescription ? "normal" : "italic" }}>
              <ExpandableText
                text={novel.novelDescription || "No description available."}
                truncate={truncate}
              />
            </div>
          </CardContent>
        )}
      </>
    </Card>
  );
}

export { NovelCard };
