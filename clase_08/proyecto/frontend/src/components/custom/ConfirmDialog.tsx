import { useRef, useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
import { cn } from "../../lib/utils";

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void | Promise<void>;
  disabled?: boolean;
  destructive?: boolean;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  onConfirm,
  disabled = false,
  destructive = false,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);

  const confirm = async () => {
    if (pendingRef.current || disabled) return;
    pendingRef.current = true;
    setPending(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  };

  return (
    <AlertDialog
      open={open}
      onOpenChange={(nextOpen) => !pending && onOpenChange(nextOpen)}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel
            disabled={pending || disabled}
            aria-busy={pending || undefined}
          >
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            className={cn(destructive && "button-destructive")}
            disabled={pending || disabled}
            aria-busy={pending || undefined}
            onClick={(event) => {
              event.preventDefault();
              void confirm();
            }}
          >
            {pending ? "Procesando…" : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
