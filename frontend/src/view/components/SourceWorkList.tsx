import { type SourceWorkData } from "@/types/novel";
import { SourceWorkCard } from "./SourceWorkCard";

function SourceWorkList({ data } : { data : SourceWorkData[] }) {
    return (
        <div className="space-y-4">
            {data.map((item) => (
                <SourceWorkCard key={item.sourceWork.sourceWorkId} sourceWork={item.sourceWork} novels={item.novels} />
            ))}
        </div>
    )
}

export {
    SourceWorkList
}