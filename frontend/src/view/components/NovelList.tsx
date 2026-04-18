import { NovelCard } from "./NovelCard";
import { type Novel } from "@/types/novel";

function NovelList({novels, showDescription=false} : {novels : Novel[], showDescription? : boolean}) {
    return <div className="flex flex-col flex-start gap-4">{novels.map(novel => <NovelCard key={novel.novelId} novel={novel} showDescription={showDescription} />)}</div>
}

export {
    NovelList
}
