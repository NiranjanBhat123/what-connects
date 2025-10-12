import React from "react";
import { cn } from "@/lib/utils"; // keep this if you have a utility for classnames

const Progress = React.forwardRef(({ className, value = 0, max = 100, ...props }, ref) => {
    const percent = Math.min(Math.max(value / max, 0), 1) * 100;

    return (
        <div
            ref={ref}
            className={cn("relative h-2 w-full overflow-hidden rounded-full bg-muted", className)}
            {...props}
        >
            <div
                className="h-full bg-primary transition-all"
                style={{ width: `${percent}%` }}
            />
        </div>
    );
});

Progress.displayName = "Progress";

export { Progress };
