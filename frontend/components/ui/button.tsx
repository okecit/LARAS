import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/format";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/60 disabled:pointer-events-none disabled:opacity-40 [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-teal text-bg hover:bg-teal/90 font-semibold",
        secondary: "bg-panel2 text-ink border border-line2 hover:border-teal/50 hover:text-teal",
        ghost: "text-mute hover:bg-panel2 hover:text-ink",
        outline: "border border-line2 text-ink hover:border-teal/60 hover:text-teal",
        danger: "bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25",
      },
      size: { default: "h-8 px-3", sm: "h-7 px-2.5 text-2xs", lg: "h-10 px-4 text-sm", icon: "h-8 w-8" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
});
Button.displayName = "Button";
