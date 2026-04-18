import {Input} from "@/components/ui/input";
import { useState } from "react";
import { Button } from "../../components/ui/button";

function StaticRouteInput({ toHref, defaultValue }: { toHref : (search : string) => string, defaultValue? : string }) {
    const [searchTerm, setSearchTerm] = useState<string>(defaultValue || "");
    const [isComposing, setIsComposing] = useState<boolean>(false);

    return (
        <form className="flex gap-2" onSubmit={() => {
            if (!isComposing) window.location.href = toHref(searchTerm)
        }}>
            <Input
                name="search"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onCompositionStart={(e) => {
                    setIsComposing(true);
                    e.stopPropagation();
                }}
                onCompositionEnd={(e) => {
                    setIsComposing(false);
                    e.stopPropagation();
                }}
                placeholder="Search..."
                className="flex-1"
            />
            <Button type="submit">Search</Button>
        </form>
    )
}

export {
    StaticRouteInput
}