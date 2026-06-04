import { Input } from "@/components/ui/input";
import { useState } from "react";
import { Button } from "../../components/ui/button";
import { useNavigate } from "react-router-dom";

function StaticRouteInput({
  toHref,
  defaultValue,
}: {
  toHref: (search: string) => string;
  defaultValue?: string;
}) {
  const [searchTerm, setSearchTerm] = useState<string>(defaultValue || "");
  const [isComposing, setIsComposing] = useState<boolean>(false);
  const navigate = useNavigate();

  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (!isComposing)
          navigate(toHref(searchTerm))?.catch((err) => {
            console.error("Failed to navigate", err);
          });
      }}
    >
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
  );
}

export { StaticRouteInput };
