import React from "react";
import { cn } from "@/lib/utils"; // your classnames helper

const Label = React.forwardRef(({ className, children, ...props }, ref) => {
    return (
        <label
            ref={ref}
            className={cn("block text-sm font-medium leading-4 text-foreground", className)}
            {...props}
        >
            {children}
        </label>
    );
});

Label.displayName = "Label";

export { Label };
