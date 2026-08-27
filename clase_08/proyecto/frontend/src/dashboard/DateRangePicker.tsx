import { format } from "date-fns";
import { DateRangePicker as DvemDateRangePicker } from "../components/ui/date-range-picker";

export type DashboardDateRange = { from: string; to: string };

type Props = {
    range: DashboardDateRange;
    onApply: (range: DashboardDateRange) => void;
};

const toDate = (value: string): Date => {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
};

export function DateRangePicker({ range, onApply }: Props) {
    return (
        <DvemDateRangePicker
            initialDateFrom={toDate(range.from)}
            initialDateTo={toDate(range.to)}
            showCompare={false}
            mobileLayout
            align="end"
            triggerClassName="w-full sm:w-auto"
            onUpdate={({ range: nextRange }) => {
                if (!nextRange.from || !nextRange.to) return;
                onApply({
                    from: format(nextRange.from, "yyyy-MM-dd"),
                    to: format(nextRange.to, "yyyy-MM-dd"),
                });
            }}
        />
    );
}
