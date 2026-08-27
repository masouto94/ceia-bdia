import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useState, type ComponentPropsWithoutRef } from "react";
import { cn } from "../../lib/utils";

type PasswordInputProps = Omit<ComponentPropsWithoutRef<"input">, "type">;

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, ...props }, ref) => {
    const [visible, setVisible] = useState(false);
    const label = visible ? "Ocultar contraseña" : "Mostrar contraseña";

    return (
      <span className="password-input">
        <input
          ref={ref}
          className={cn("password-input-control", className)}
          type={visible ? "text" : "password"}
          {...props}
        />
        <button
          type="button"
          className="password-visibility-toggle"
          aria-label={label}
          aria-pressed={visible}
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
        </button>
      </span>
    );
  },
);
PasswordInput.displayName = "PasswordInput";
