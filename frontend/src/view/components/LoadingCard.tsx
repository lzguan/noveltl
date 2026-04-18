import { Skeleton } from "@/components/ui/skeleton"; 
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function LoadingCard() {
    return (
        <Card className="text-left">
            <CardHeader>
                <CardTitle>
                    <Skeleton className="h-6 w-1/2" />
                </CardTitle>
            </CardHeader>
            <CardContent>
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
            </CardContent>
        </Card>
    )
}

export {
    LoadingCard
}