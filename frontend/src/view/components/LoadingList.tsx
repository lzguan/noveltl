import { LoadingCard } from "./LoadingCard";

function LoadingList() {
    return (
        <div className="space-y-4">
            <LoadingCard />
            <LoadingCard />
            <LoadingCard />
        </div>
    )
}

export {
    LoadingList
}