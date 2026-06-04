import type { SourceWorkDataOutput } from "@/client";
import { SourceWorkCard } from "./SourceWorkCard";

function SourceWorkList({ data }: { data: SourceWorkDataOutput[] }) {
  return (
    <div className="space-y-4">
      {data.map((item) => (
        <SourceWorkCard
          key={item.sourceWork.sourceWorkId}
          sourceWork={item.sourceWork}
          novels={item.novels}
        />
      ))}
    </div>
  );
}

export { SourceWorkList };
