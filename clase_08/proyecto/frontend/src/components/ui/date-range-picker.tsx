"use client";

import {
  type FC,
  useState,
  useRef,
  type JSX,
  useEffect,
  type HTMLAttributes,
} from "react";
import { Button } from "./button";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./dialog";
import { Calendar } from "./calendar";
import { Label } from "./label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./select";
import { Switch } from "./switch";
import { CalendarIcon, ChevronDown, ChevronUp, Check } from "lucide-react";
import { cn } from "../../lib/utils";
import type { DateRange } from "react-day-picker";
import { es } from "date-fns/locale";

const DialogHeader = ({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>): JSX.Element => (
  <div className={className} {...props} />
);

export interface DateRangePickerProps {
  onUpdate?: (values: { range: DateRange; rangeCompare?: DateRange }) => void;
  initialDateFrom?: Date | string;
  initialDateTo?: Date | string;
  initialCompareFrom?: Date | string;
  initialCompareTo?: Date | string;
  align?: "start" | "center" | "end";
  locale?: string;
  showCompare?: boolean;
  mobileLayout?: boolean;
  triggerClassName?: string;
}

const formatDate = (date: Date, locale: string = "es"): string => {
  return date.toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const getDateAdjustedForTimezone = (dateInput: Date | string): Date => {
  if (typeof dateInput === "string") {
    const parts = dateInput.split("-").map((part) => parseInt(part, 10));
    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    return date;
  } else {
    return dateInput;
  }
};

const getPreviousCalendarYearDate = (date: Date): Date => {
  const previousYear = date.getFullYear() - 1;
  const lastDayOfMonth = new Date(
    previousYear,
    date.getMonth() + 1,
    0,
  ).getDate();

  return new Date(
    previousYear,
    date.getMonth(),
    Math.min(date.getDate(), lastDayOfMonth),
  );
};

interface DateBoundaryPickerProps {
  label: string;
  testId: string;
  locale: string;
  value: Date | undefined;
  onSelect: (date: Date) => void;
  side?: React.ComponentProps<typeof PopoverContent>["side"];
  align?: React.ComponentProps<typeof PopoverContent>["align"];
  className?: string;
}

const DateBoundaryPicker = ({
  label,
  testId,
  locale,
  value,
  onSelect,
  side,
  align = "start",
  className,
}: DateBoundaryPickerProps): JSX.Element => {
  const [open, setOpen] = useState(false);

  return (
    <div
      data-testid={`${testId}-container`}
      className={cn("min-w-0", className)}
    >
      <Label className="mb-1 block text-xs">{label}</Label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            data-testid={testId}
            className="min-h-11 w-full min-w-0 justify-between px-2 text-xs font-normal"
            aria-label={`${label}: ${value ? formatDate(value, locale) : "sin fecha"}`}
          >
            <span className="truncate">
              {value ? formatDate(value, locale) : "Seleccionar"}
            </span>
            <CalendarIcon data-icon="inline-end" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          portalled={false}
          side={side}
          align={align}
          className="z-[202] w-auto p-0"
          collisionPadding={8}
        >
          <Calendar
            mode="single"
            selected={value}
            onSelect={(date) => {
              if (!date) return;
              setOpen(false);
              onSelect(date);
            }}
            defaultMonth={value}
            locale={es}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  );
};

interface Preset {
  name: string;
  label: string;
}

const PRESETS: Preset[] = [
  { name: "today", label: "Hoy" },
  { name: "yesterday", label: "Ayer" },
  { name: "last7", label: "Últimos 7 días" },
  { name: "last14", label: "Últimos 14 días" },
  { name: "last30", label: "Últimos 30 días" },
  { name: "thisWeek", label: "Esta semana" },
  { name: "lastWeek", label: "Semana pasada" },
  { name: "thisMonth", label: "Este mes" },
  { name: "lastMonth", label: "Mes pasado" },
];

export const DateRangePicker: FC<DateRangePickerProps> = ({
  initialDateFrom = new Date(new Date().setHours(0, 0, 0, 0)),
  initialDateTo,
  initialCompareFrom,
  initialCompareTo,
  onUpdate,
  align = "end",
  locale = "es",
  showCompare = true,
  mobileLayout = false,
  triggerClassName,
}): JSX.Element => {
  const [isOpen, setIsOpen] = useState(false);

  const [range, setRange] = useState<DateRange>({
    from: getDateAdjustedForTimezone(initialDateFrom),
    to: initialDateTo
      ? getDateAdjustedForTimezone(initialDateTo)
      : getDateAdjustedForTimezone(initialDateFrom),
  });
  const [calendarMonth, setCalendarMonth] = useState(() =>
    getDateAdjustedForTimezone(initialDateFrom),
  );

  const [rangeCompare, setRangeCompare] = useState<DateRange | undefined>(
    initialCompareFrom
      ? {
          from: new Date(new Date(initialCompareFrom).setHours(0, 0, 0, 0)),
          to: initialCompareTo
            ? new Date(new Date(initialCompareTo).setHours(0, 0, 0, 0))
            : new Date(new Date(initialCompareFrom).setHours(0, 0, 0, 0)),
        }
      : undefined,
  );

  const openedRangeRef = useRef<DateRange | undefined>(undefined);
  const openedRangeCompareRef = useRef<DateRange | undefined>(undefined);

  const [isSmallScreen, setIsSmallScreen] = useState(
    typeof window !== "undefined" ? window.innerWidth < 960 : false,
  );
  const [isWideShortLandscape, setIsWideShortLandscape] = useState(
    typeof window !== "undefined"
      ? window.innerWidth >= 700 &&
          window.innerWidth > window.innerHeight &&
          window.innerHeight <= 600
      : false,
  );

  // Still need this effect for window resize, which is a genuine external subscription
  useEffect(() => {
    const handleResize = (): void => {
      setIsSmallScreen(window.innerWidth < 960);
      setIsWideShortLandscape(
        window.innerWidth >= 700 &&
          window.innerWidth > window.innerHeight &&
          window.innerHeight <= 600,
      );
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  const getPresetRange = (presetName: string): DateRange => {
    const preset = PRESETS.find(({ name }) => name === presetName);
    if (!preset) throw new Error(`Unknown date range preset: ${presetName}`);
    const from = new Date();
    const to = new Date();
    const first = from.getDate() - from.getDay();

    switch (preset.name) {
      case "today":
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "yesterday":
        from.setDate(from.getDate() - 1);
        from.setHours(0, 0, 0, 0);
        to.setDate(to.getDate() - 1);
        to.setHours(23, 59, 59, 999);
        break;
      case "last7":
        from.setDate(from.getDate() - 6);
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "last14":
        from.setDate(from.getDate() - 13);
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "last30":
        from.setDate(from.getDate() - 29);
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "thisWeek":
        from.setDate(first);
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "lastWeek":
        from.setDate(from.getDate() - 7 - from.getDay());
        to.setDate(to.getDate() - to.getDay() - 1);
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "thisMonth":
        from.setDate(1);
        from.setHours(0, 0, 0, 0);
        to.setHours(23, 59, 59, 999);
        break;
      case "lastMonth":
        from.setMonth(from.getMonth() - 1);
        from.setDate(1);
        from.setHours(0, 0, 0, 0);
        to.setDate(0);
        to.setHours(23, 59, 59, 999);
        break;
    }

    return { from, to };
  };

  const setPreset = (preset: string): void => {
    const range = getPresetRange(preset);
    setRange(range);
    setCalendarMonth(range.from!);
    if (rangeCompare) {
      const rangeCompare = {
        from: new Date(
          range.from!.getFullYear() - 1,
          range.from!.getMonth(),
          range.from!.getDate(),
        ),
        to: range.to
          ? new Date(
              range.to.getFullYear() - 1,
              range.to.getMonth(),
              range.to.getDate(),
            )
          : undefined,
      };
      setRangeCompare(rangeCompare);
    }
  };

  // Derived state: Calculate selected preset directly in render
  const selectedPreset = PRESETS.find((preset) => {
    const presetRange = getPresetRange(preset.name);

    // Normalize dates for comparison (ignore time)
    const normalizedRangeFrom = new Date(range.from!);
    normalizedRangeFrom.setHours(0, 0, 0, 0);
    const normalizedPresetFrom = new Date(presetRange.from!.getTime());
    normalizedPresetFrom.setHours(0, 0, 0, 0);

    const normalizedRangeTo = new Date(range.to ?? 0);
    normalizedRangeTo.setHours(0, 0, 0, 0);
    const normalizedPresetTo = new Date(presetRange.to?.getTime() ?? 0);
    normalizedPresetTo.setHours(0, 0, 0, 0);

    return (
      normalizedRangeFrom.getTime() === normalizedPresetFrom.getTime() &&
      normalizedRangeTo.getTime() === normalizedPresetTo.getTime()
    );
  })?.name;

  const restoreOpenedValues = (): void => {
    if (openedRangeRef.current) {
      setRange(openedRangeRef.current);
      setCalendarMonth(openedRangeRef.current.from!);
    }
    setRangeCompare(openedRangeCompareRef.current);
  };

  const PresetButton = ({
    preset,
    label,
    isSelected,
  }: {
    preset: string;
    label: string;
    isSelected: boolean;
  }): JSX.Element => (
    <Button
      className={cn(
        "w-full justify-start whitespace-nowrap px-2",
        isSelected && "pointer-events-none",
        "[@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:h-8",
      )}
      variant="ghost"
      onClick={() => {
        setPreset(preset);
      }}
    >
      <>
        <span className={cn("pr-2 opacity-0", isSelected && "opacity-70")}>
          <Check width={18} height={18} />
        </span>
        {label}
      </>
    </Button>
  );

  const areRangesEqual = (a?: DateRange, b?: DateRange): boolean => {
    if (!a || !b) return a === b;
    return (
      a.from?.getTime() === b.from?.getTime() &&
      ((!a.to && !b.to) ||
        (a.to != null && b.to != null && a.to.getTime() === b.to.getTime()))
    );
  };

  const isMobileDialog = mobileLayout && isSmallScreen;

  const handleOpenChange = (open: boolean): void => {
    if (!open) {
      restoreOpenedValues();
    } else {
      openedRangeRef.current = range;
      openedRangeCompareRef.current = rangeCompare;
      setCalendarMonth(range.from!);
    }
    setIsOpen(open);
  };

  const trigger = (
    <Button
      variant="outline"
      className={cn(
        mobileLayout && "min-h-11 w-full justify-between",
        triggerClassName,
      )}
    >
      <div className="text-right">
        <div className="py-1">
          <div>{`${formatDate(range.from!, locale)}${
            range.to != null ? " - " + formatDate(range.to, locale) : ""
          }`}</div>
        </div>
        {rangeCompare != null && (
          <div className="-mt-1 text-xs opacity-60">
            vs. {formatDate(rangeCompare.from!, locale)}
            {rangeCompare.to != null
              ? ` - ${formatDate(rangeCompare.to, locale)}`
              : ""}
          </div>
        )}
      </div>
      <div className="-mr-2 scale-125 pl-1 opacity-60">
        {isOpen ? <ChevronUp width={24} /> : <ChevronDown width={24} />}
      </div>
    </Button>
  );

  const pickerContent = (
    <>
      {isMobileDialog ? (
        <DialogHeader className="shrink-0 gap-1 px-2 pt-1 pr-12 text-left">
          <DialogTitle>Seleccionar rango de fechas</DialogTitle>
          <DialogDescription className="sr-only">
            Elegí las fechas y actualizá el período del dashboard.
          </DialogDescription>
        </DialogHeader>
      ) : (
        <h2 className="px-4 pt-3 text-lg font-semibold leading-none tracking-tight">
          Seleccionar rango de fechas
        </h2>
      )}
      <div
        data-testid="date-range-picker-body"
        className={cn(
          "flex py-2",
          mobileLayout && "w-full px-2",
          mobileLayout && !isMobileDialog && "min-h-0 flex-1 overflow-y-auto",
          isMobileDialog &&
            "py-0 [@media(orientation:landscape)_and_(max-height:600px)]:min-h-0 [@media(orientation:landscape)_and_(max-height:600px)]:flex-1 [@media(orientation:landscape)_and_(max-height:600px)]:overflow-y-auto [@media(orientation:landscape)_and_(min-width:700px)_and_(min-height:360px)_and_(max-height:600px)]:flex-none [@media(orientation:landscape)_and_(min-width:700px)_and_(min-height:360px)_and_(max-height:600px)]:overflow-visible [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:px-3",
        )}
      >
        <div
          data-testid="date-range-picker-main"
          className={cn(
            "flex",
            mobileLayout && "w-full",
            isWideShortLandscape && "min-w-0 flex-1",
          )}
        >
          <div className={cn("flex flex-col", mobileLayout && "w-full")}>
            <div
              className={cn(
                "flex flex-col lg:flex-row gap-2 px-3 justify-end items-center lg:items-start pb-4 lg:pb-0",
                mobileLayout && "w-full px-1",
                isMobileDialog && "pb-1",
              )}
            >
              {showCompare && (
                <div className="flex items-center space-x-2 pr-4 py-1">
                  <Switch
                    defaultChecked={Boolean(rangeCompare)}
                    onCheckedChange={(checked: boolean) => {
                      if (checked) {
                        if (!range.to) {
                          setRange({
                            from: range.from,
                            to: range.from,
                          });
                        }
                        setRangeCompare({
                          from: getPreviousCalendarYearDate(range.from!),
                          to: range.to
                            ? getPreviousCalendarYearDate(range.to)
                            : getPreviousCalendarYearDate(range.from!),
                        });
                      } else {
                        setRangeCompare(undefined);
                        setCalendarMonth(range.from!);
                      }
                    }}
                    id="compare-mode"
                  />
                  <Label htmlFor="compare-mode">Comparar</Label>
                </div>
              )}
              <div
                data-testid="date-range-picker-controls"
                className={cn("flex flex-col gap-2", mobileLayout && "w-full")}
              >
                <div
                  className={cn(
                    "flex gap-2",
                    mobileLayout && "grid w-full grid-cols-2 gap-2",
                  )}
                >
                  <DateBoundaryPicker
                    label="Fecha desde"
                    testId="date-boundary-from"
                    locale={locale}
                    value={range.from}
                    className={cn(isSmallScreen ? "w-full" : "w-52 shrink-0")}
                    onSelect={(date) => {
                      setRange({
                        from: date,
                        to:
                          range.to == null || date > range.to ? date : range.to,
                      });
                      setCalendarMonth(date);
                    }}
                  />
                  {!mobileLayout && <div className="py-1">-</div>}
                  <DateBoundaryPicker
                    label="Fecha hasta"
                    testId="date-boundary-to"
                    locale={locale}
                    value={range.to}
                    className={cn(isSmallScreen ? "w-full" : "w-52 shrink-0")}
                    onSelect={(date) => {
                      setRange({
                        from: date < range.from! ? date : range.from!,
                        to: date,
                      });
                      setCalendarMonth(date);
                    }}
                  />
                </div>
                {rangeCompare != null && (
                  <div className="flex gap-2">
                    <DateBoundaryPicker
                      label="Comparación desde"
                      testId="compare-date-boundary-from"
                      locale={locale}
                      value={rangeCompare?.from}
                      className={cn(isSmallScreen ? "w-full" : "w-52 shrink-0")}
                      onSelect={(date) => {
                        setRangeCompare({
                          from: date,
                          to:
                            rangeCompare.to == null || date > rangeCompare.to
                              ? date
                              : rangeCompare.to,
                        });
                      }}
                    />
                    <div className="py-1">-</div>
                    <DateBoundaryPicker
                      label="Comparación hasta"
                      testId="compare-date-boundary-to"
                      locale={locale}
                      value={rangeCompare?.to}
                      className={cn(isSmallScreen ? "w-full" : "w-52 shrink-0")}
                      onSelect={(date) => {
                        setRangeCompare({
                          from:
                            date < rangeCompare.from!
                              ? date
                              : rangeCompare.from,
                          to: date,
                        });
                      }}
                    />
                  </div>
                )}
                {isSmallScreen && !isWideShortLandscape && (
                  <div className="min-w-0">
                    <Label className="sr-only mb-1 text-xs">Período</Label>
                    <Select
                      value={selectedPreset ?? ""}
                      onValueChange={(value) => {
                        setPreset(value);
                      }}
                    >
                      <SelectTrigger
                        className={cn(
                          "mx-auto mb-1 w-[180px]",
                          mobileLayout && "min-h-11 w-full",
                        )}
                      >
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectContent
                        className={cn(isMobileDialog && "z-[202]")}
                      >
                        <SelectGroup>
                          {PRESETS.map((preset) => (
                            <SelectItem key={preset.name} value={preset.name}>
                              {preset.label}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
            </div>
            <div className={cn(mobileLayout && "flex w-full justify-center")}>
              <Calendar
                key={`${calendarMonth.getFullYear()}-${calendarMonth.getMonth()}`}
                data-testid="date-range-picker-calendar"
                className={cn(
                  mobileLayout && "w-full",
                  isMobileDialog && "p-1 [--cell-size:--spacing(11)]",
                  isMobileDialog &&
                    "[@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:p-0 [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:[--cell-size:--spacing(6)] [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:[&_.rdp-month]:gap-1 [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:[&_.rdp-week]:mt-0.5 [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:[&_.rdp-day]:h-6 [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:[&_.rdp-day_button]:!h-6 [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:[&_.rdp-day_button]:!min-h-0",
                )}
                mode="range"
                onSelect={(value: { from?: Date; to?: Date } | undefined) => {
                  if (value?.from) {
                    setRange({ from: value.from, to: value.to });
                    setCalendarMonth(value.from);
                  }
                }}
                selected={range}
                numberOfMonths={isSmallScreen && !isWideShortLandscape ? 1 : 2}
                month={calendarMonth}
                onMonthChange={setCalendarMonth}
                locale={es}
              />
            </div>
          </div>
        </div>
        {(!isSmallScreen || isWideShortLandscape) && (
          <div
            data-testid="date-range-picker-preset-sidebar"
            className={cn(
              "flex w-40 shrink-0 flex-col items-stretch gap-1 px-1 pb-6",
              isWideShortLandscape && "w-36 pb-0",
            )}
          >
            <div
              className={cn(
                "flex w-full flex-col items-stretch gap-1",
                isWideShortLandscape && "gap-0",
              )}
            >
              {PRESETS.map((preset) => (
                <PresetButton
                  key={preset.name}
                  preset={preset.name}
                  label={preset.label}
                  isSelected={selectedPreset === preset.name}
                />
              ))}
            </div>
          </div>
        )}
      </div>
      <div
        className={cn(
          "flex justify-end gap-2 py-2 pr-4",
          mobileLayout &&
            !isMobileDialog &&
            "sticky bottom-0 grid w-full shrink-0 grid-cols-2 bg-popover px-2 pr-2 sm:flex",
          isMobileDialog &&
            "grid w-full shrink-0 grid-cols-2 px-2 py-2 pr-2 [@media(orientation:landscape)_and_(max-height:600px)]:py-1",
        )}
      >
        <Button
          onClick={() => {
            handleOpenChange(false);
          }}
          variant="outline"
          className={cn(
            "active:bg-accent active:text-accent-foreground",
            mobileLayout && "min-h-11 w-full",
            mobileLayout && !isMobileDialog && "sm:w-auto sm:flex-none",
          )}
        >
          Cancelar
        </Button>
        <Button
          className={cn(
            mobileLayout && "min-h-11 w-full",
            mobileLayout && !isMobileDialog && "sm:w-auto sm:flex-none",
          )}
          onClick={() => {
            setIsOpen(false);
            if (
              !areRangesEqual(range, openedRangeRef.current) ||
              !areRangesEqual(rangeCompare, openedRangeCompareRef.current)
            ) {
              onUpdate?.({ range, rangeCompare });
            }
          }}
        >
          Actualizar
        </Button>
      </div>
    </>
  );

  if (isMobileDialog) {
    return (
      <Dialog open={isOpen} onOpenChange={handleOpenChange}>
        <DialogTrigger asChild>{trigger}</DialogTrigger>
        <DialogContent
          data-testid="date-range-picker-dialog"
          className="max-h-none w-[calc(100vw-2rem)] max-w-md gap-1 overflow-visible p-2 [@media(orientation:landscape)_and_(max-height:600px)]:flex [@media(orientation:landscape)_and_(max-height:600px)]:max-h-[calc(100dvh-1rem)] [@media(orientation:landscape)_and_(max-height:600px)]:flex-col [@media(orientation:landscape)_and_(max-height:600px)]:overflow-hidden [@media(orientation:landscape)_and_(min-width:700px)_and_(max-height:600px)]:max-w-3xl [&>button]:flex [&>button]:size-11 [&>button]:items-center [&>button]:justify-center"
        >
          {pickerContent}
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Popover modal open={isOpen} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        align={align}
        avoidCollisions
        collisionPadding={mobileLayout ? 16 : 8}
        sideOffset={mobileLayout ? 8 : 4}
        sticky="always"
        className={cn(
          "w-[46rem] max-w-[calc(100vw-2rem)] p-0",
          mobileLayout &&
            "flex max-h-[var(--radix-popover-content-available-height)] flex-col overflow-hidden",
        )}
      >
        {pickerContent}
      </PopoverContent>
    </Popover>
  );
};

export const DatePickerWithRange = DateRangePicker;
