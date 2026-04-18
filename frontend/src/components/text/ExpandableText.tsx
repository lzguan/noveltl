import { useState } from "react"

function ExpandableText({ text, truncate } : { text : string, truncate : (t : string) => {truncated : string, canTruncate : boolean} }) {
    const [expanded, setExpanded] = useState<boolean>(false)

    const truncated = truncate(text)
    return (
        <div style={{whiteSpace : "pre-wrap"}}>
            {expanded ? text : truncated.truncated}
            {truncated.canTruncate ? <button className="m-0 inline p-0 align-baseline text-inherit underline cursor-pointer bg-transparent border-0" onClick={() => setExpanded(!expanded)} >{expanded ? " <<less" : " more>>"}</button> : <></>}
        </div>
    )
}

export {
    ExpandableText
}