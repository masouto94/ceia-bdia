import type { HTMLAttributes } from "react"
import { cn } from "../../lib/utils"

export const FieldGroup = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div className={cn("field-group", className)} {...props} />
export const Field = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div className={cn("field", className)} {...props} />
export const FieldError = ({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) => <p className={cn("field-error", className)} role="alert" {...props} />
