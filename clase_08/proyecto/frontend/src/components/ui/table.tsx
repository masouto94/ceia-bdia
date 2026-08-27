import type { ComponentProps } from "react";
export const Table = (props: ComponentProps<"table">) => <table {...props} />;
export const TableHeader = (props: ComponentProps<"thead">) => <thead {...props} />;
export const TableBody = (props: ComponentProps<"tbody">) => <tbody {...props} />;
export const TableRow = (props: ComponentProps<"tr">) => <tr {...props} />;
export const TableHead = (props: ComponentProps<"th">) => <th {...props} />;
export const TableCell = (props: ComponentProps<"td">) => <td {...props} />;
