import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import type { ButtonHTMLAttributes } from "react"
import { cn } from "../../lib/utils"

const variants = cva("button", { variants: { variant: { default: "button-primary", ghost: "button-ghost", outline: "button-outline" } }, defaultVariants: { variant: "default" } })
type Props = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants> & { asChild?: boolean }
export function Button({ className, variant, asChild, ...props }: Props) { const Component = asChild ? Slot : "button"; return <Component className={cn(variants({ variant, className }))} {...props} /> }
