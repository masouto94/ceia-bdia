import {
  cloneElement,
  createContext,
  isValidElement,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
  useContext,
  useId,
  useState,
} from "react";

type TooltipContextValue = {
  contentId: string;
  visible: boolean;
  setVisible: (visible: boolean) => void;
};

const TooltipContext = createContext<TooltipContextValue | null>(null);

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function Tooltip({ children }: { children: ReactNode }) {
  const [visible, setVisible] = useState(false);
  const contentId = useId();

  return (
    <TooltipContext.Provider value={{ contentId, visible, setVisible }}>
      <span className="tooltip">{children}</span>
    </TooltipContext.Provider>
  );
}

type TriggerProps = {
  "aria-describedby"?: string;
  onBlur?: () => void;
  onFocus?: () => void;
  onKeyDown?: (event: KeyboardEvent) => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
};

export function TooltipTrigger({
  children,
}: {
  children: ReactElement<TriggerProps>;
}) {
  const context = useContext(TooltipContext);
  if (!context || !isValidElement(children)) return children;

  const { contentId, setVisible, visible } = context;
  const child = children as ReactElement<TriggerProps>;
  const describedBy = child.props["aria-describedby"];

  return cloneElement(child, {
    "aria-describedby": visible
      ? [describedBy, contentId].filter(Boolean).join(" ")
      : describedBy,
    onBlur: () => {
      child.props.onBlur?.();
      setVisible(false);
    },
    onFocus: () => {
      child.props.onFocus?.();
      setVisible(true);
    },
    onKeyDown: (event) => {
      child.props.onKeyDown?.(event);
      if (event.key === "Escape") setVisible(false);
    },
    onMouseEnter: () => {
      child.props.onMouseEnter?.();
      setVisible(true);
    },
    onMouseLeave: () => {
      child.props.onMouseLeave?.();
      setVisible(false);
    },
  });
}

export function TooltipContent({ children }: { children: ReactNode }) {
  const context = useContext(TooltipContext);
  if (!context?.visible) return null;

  return (
    <span id={context.contentId} role="tooltip" className="tooltip-content">
      {children}
    </span>
  );
}
