import { NovelList } from "./NovelList";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { routeTo } from "@/routes";
import { Button } from "@/components/ui/button";
import { ExpandableText } from "@/components/text/ExpandableText";
import { truncateProducer } from "../utils/truncateProducer";
import type { Novel, SourceWork } from "@/client";
import { Link } from "react-router-dom";

const truncate = truncateProducer(300)

function SourceWorkCard({ sourceWork, novels } : { sourceWork : SourceWork, novels : Novel[] }) {
    return (
        <Card className="text-left">
            <CardHeader>
                <CardTitle>{<Link className="hover:underline" to={routeTo.view.sourcework(sourceWork.sourceWorkId)}>
                    {sourceWork.sourceWorkTitle}
                </Link>}</CardTitle>
                <CardDescription>
                    <div style={{ fontStyle: sourceWork.sourceWorkDescription ? "normal" : "italic" }}>
                        {sourceWork.sourceWorkDescription ? <ExpandableText text={sourceWork.sourceWorkDescription} truncate={truncate} /> : "No description available."}
                    </div>
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Collapsible className="rounded-md data-[state=open]:bg-muted">
                    <CollapsibleTrigger asChild>
                        <Button variant="ghost" className="group w-full">View Novels</Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <NovelList novels={novels} />
                    </CollapsibleContent>
                </Collapsible>
            </CardContent>
        </Card>
    )
}

export {
    SourceWorkCard
}
