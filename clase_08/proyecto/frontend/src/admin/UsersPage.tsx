import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Info,
  Pencil,
  Plus,
  Search,
  UserRoundCheck,
  UserRoundX,
} from "lucide-react";
import * as api from "../api";
import { Badge } from "../components/ui/badge";
import { RowActions, type RowAction } from "../components/custom/RowActions";
import { ConfirmDialog } from "../components/custom/ConfirmDialog";
import { Button } from "../components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../components/ui/dialog";
import { Field, FieldError, FieldGroup } from "../components/ui/field";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";

const roleLabels: Record<api.MemberRole, string> = {
  admin: "Administración",
  member: "Integrante",
  viewer: "Consulta",
};
const statusLabels: Record<api.MemberStatus, string> = {
  active: "Activo",
  inactive: "Inactivo",
};
const sizes = [10, 20, 30, 40, 50];
const defaults: api.MembersQuery = {
  page: 1,
  per_page: 10,
  search: "",
  role: "",
  status: "",
  sort: "email:asc",
};

function queryFrom(params: URLSearchParams): api.MembersQuery {
  const page = Number(params.get("page"));
  const perPage = Number(params.get("per_page"));
  const role = params.get("role");
  const status = params.get("status");
  return {
    page: page > 0 ? page : 1,
    per_page: sizes.includes(perPage) ? perPage : 10,
    search: params.get("search") ?? "",
    role:
      role === "admin" || role === "member" || role === "viewer" ? role : "",
    status: status === "active" || status === "inactive" ? status : "",
    sort: params.get("sort") ?? defaults.sort,
  };
}
function passwordLabel(member: api.Member) {
  return member.password_setup_required
    ? "Contraseña pendiente"
    : "Contraseña configurada";
}
function MemberLabels({ member }: { member: api.Member }) {
  return (
    <>
      <Badge>{roleLabels[member.role]}</Badge>
      <Badge>{statusLabels[member.status]}</Badge>
      <Badge>{passwordLabel(member)}</Badge>
    </>
  );
}

function DetailsDialog({
  member,
  open,
  onOpenChange,
}: {
  member: api.Member | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!member) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="member-details-description">
        <div className="dialog-header">
          <DialogTitle>Detalles de la persona</DialogTitle>
          <DialogDescription id="member-details-description">
            Información de acceso al espacio de trabajo.
          </DialogDescription>
        </div>
        <dl className="details-list">
          <div>
            <dt>Correo electrónico</dt>
            <dd>{member.email}</dd>
          </div>
          <div>
            <dt>Rol</dt>
            <dd>{roleLabels[member.role]}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{statusLabels[member.status]}</dd>
          </div>
          <div>
            <dt>Configuración</dt>
            <dd>{passwordLabel(member)}</dd>
          </div>
        </dl>
        <div className="dialog-footer">
          <DialogClose asChild>
            <Button variant="outline">Cerrar</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CreateDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (message: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<api.MemberRole>("viewer");
  const [touched, setTouched] = useState(false);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setTouched(true);
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      await api.createMember(email, role);
      onCreated(
        "La persona fue agregada. Podrá establecer su contraseña desde recuperación.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "No se pudo agregar a la persona.",
      );
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => !submitting && onOpenChange(nextOpen)}
    >
      <DialogContent aria-describedby="create-member-description">
        <div className="dialog-header">
          <DialogTitle>Agregar persona</DialogTitle>
          <DialogDescription id="create-member-description">
            Otorgá acceso al espacio de trabajo.
          </DialogDescription>
        </div>
        <form noValidate onSubmit={submit}>
          <FieldGroup>
            <Field data-invalid={(touched && !valid) || undefined}>
              <label htmlFor="member-email">Correo electrónico</label>
              <input
                id="member-email"
                type="email"
                value={email}
                disabled={submitting}
                onChange={(event) => setEmail(event.target.value)}
                onBlur={() => setTouched(true)}
                aria-invalid={(touched && !valid) || undefined}
                aria-describedby={
                  touched && !valid ? "member-email-error" : undefined
                }
              />
              {touched && !valid && (
                <FieldError id="member-email-error">
                  Ingresá un correo electrónico válido.
                </FieldError>
              )}
            </Field>
            <Field>
              <label htmlFor="member-role">Rol</label>
              <select
                id="member-role"
                value={role}
                disabled={submitting}
                onChange={(event) =>
                  setRole(event.target.value as api.MemberRole)
                }
              >
                <option value="admin">Administración</option>
                <option value="member">Integrante</option>
                <option value="viewer">Consulta</option>
              </select>
            </Field>
            <div className="dialog-footer">
              <DialogClose asChild>
                <Button
                  type="button"
                  variant="outline"
                  disabled={submitting}
                  aria-busy={submitting || undefined}
                >
                  Cancelar
                </Button>
              </DialogClose>
              <Button
                type="submit"
                disabled={submitting}
                aria-busy={submitting || undefined}
              >
                {submitting ? "Agregando…" : "Agregar persona"}
              </Button>
            </div>
            {message && (
              <p
                role={message.startsWith("La persona") ? "status" : "alert"}
                className={message.startsWith("La persona") ? "" : "error"}
              >
                {message}
              </p>
            )}
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditRoleDialog({
  member,
  open,
  busy,
  onOpenChange,
  onSubmit,
}: {
  member: api.Member | null;
  open: boolean;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (role: api.MemberRole) => Promise<void>;
}) {
  const [role, setRole] = useState<api.MemberRole>(
    () => member?.role ?? "viewer",
  );
  const [submitting, setSubmitting] = useState(false);
  if (!member) return null;
  const isBusy = busy || submitting;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (isBusy || role === member.role) return;
    setSubmitting(true);
    try {
      await onSubmit(role);
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => !isBusy && onOpenChange(nextOpen)}
    >
      <DialogContent aria-describedby="edit-member-role-description">
        <div className="dialog-header">
          <DialogTitle>Editar rol</DialogTitle>
          <DialogDescription id="edit-member-role-description">
            Actualizá el nivel de acceso de {member.email}.
          </DialogDescription>
        </div>
        <form noValidate onSubmit={submit}>
          <FieldGroup>
            <Field>
              <label htmlFor="edit-member-role">Rol</label>
              <select
                id="edit-member-role"
                value={role}
                disabled={isBusy}
                onChange={(event) =>
                  setRole(event.target.value as api.MemberRole)
                }
              >
                <option value="admin">Administración</option>
                <option value="member">Integrante</option>
                <option value="viewer">Consulta</option>
              </select>
            </Field>
            <div className="dialog-footer">
              <DialogClose asChild>
                <Button
                  type="button"
                  variant="outline"
                  disabled={isBusy}
                  aria-busy={isBusy || undefined}
                >
                  Cancelar
                </Button>
              </DialogClose>
              <Button
                type="submit"
                disabled={isBusy || role === member.role}
                aria-busy={isBusy || undefined}
              >
                {isBusy ? "Guardando…" : "Guardar cambios"}
              </Button>
            </div>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Pagination({
  result,
  update,
}: {
  result: api.MembersResponse;
  update: (next: Partial<api.MembersQuery>) => void;
}) {
  const first = result.page <= 1,
    last = result.page >= result.pages;
  return (
    <nav className="pagination" aria-label="Paginación de personas">
      <span>{result.total} personas</span>
      <div className="pagination-page-size">
        <label htmlFor="members-per-page">Filas por página</label>
        <select
          id="members-per-page"
          value={result.per_page}
          onChange={(event) =>
            update({ per_page: Number(event.target.value), page: 1 })
          }
        >
          {sizes.map((size) => (
            <option key={size}>{size}</option>
          ))}
        </select>
      </div>
      <span>
        Página {result.page} de {result.pages || 1}
      </span>
      <div>
        <Button
          aria-label="Primera página"
          variant="outline"
          disabled={first}
          onClick={() => update({ page: 1 })}
        >
          <ChevronsLeft />
        </Button>
        <Button
          aria-label="Página anterior"
          variant="outline"
          disabled={first}
          onClick={() => update({ page: result.page - 1 })}
        >
          <ChevronLeft />
        </Button>
        <Button
          aria-label="Página siguiente"
          variant="outline"
          disabled={last}
          onClick={() => update({ page: result.page + 1 })}
        >
          <ChevronRight />
        </Button>
        <Button
          aria-label="Última página"
          variant="outline"
          disabled={last}
          onClick={() => update({ page: result.pages })}
        >
          <ChevronsRight />
        </Button>
      </div>
    </nav>
  );
}

export function UsersPage({
  canManage,
  currentUserId,
}: {
  canManage: boolean;
  currentUserId?: string;
}) {
  const [params, setParams] = useSearchParams();
  const query = useMemo(() => queryFrom(params), [params]);
  const [success, setSuccess] = useState("");
  const [result, setResult] = useState<api.MembersResponse | null>(null);
  const [error, setError] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(query.search);
  const [selected, setSelected] = useState<api.Member | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<api.Member | null>(null);
  const [deactivating, setDeactivating] = useState<api.Member | null>(null);
  const [reactivating, setReactivating] = useState<api.Member | null>(null);
  const [pendingMemberId, setPendingMemberId] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api
      .getMembers(query)
      .then((next) => {
        if (active) setResult(next);
      })
      .catch((next) => {
        if (active)
          setError(
            next instanceof Error
              ? next.message
              : "No se pudo cargar la lista.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, retry]);
  const update = (next: Partial<api.MembersQuery>) => {
    setLoading(true);
    setError("");
    const merged = { ...query, ...next };
    const output = new URLSearchParams();
    Object.entries(merged).forEach(([key, value]) =>
      output.set(key, String(value)),
    );
    setParams(output);
  };
  const searchSubmit = (event: FormEvent) => {
    event.preventDefault();
    update({ search, page: 1 });
  };
  const mutateMember = async (
    member: api.Member,
    payload: api.MemberUpdate,
    message: string,
  ) => {
    if (pendingMemberId) return;
    setPendingMemberId(member.user_id);
    setMutationError("");
    setSuccess("");
    try {
      await api.updateMember(member.user_id, payload);
      setSuccess(message);
      setEditing(null);
      setDeactivating(null);
      setLoading(true);
      setRetry((value) => value + 1);
    } catch (next) {
      setMutationError(
        next instanceof Error
          ? next.message
          : "No se pudo actualizar a la persona.",
      );
    } finally {
      setPendingMemberId(null);
    }
  };
  const actionsFor = (member: api.Member): RowAction[] => {
    const busy = pendingMemberId === member.user_id;
    const selfDeactivation = currentUserId === member.user_id;
    const actions: RowAction[] = [
      {
        label: "Ver detalles",
        icon: Info,
        onClick: () => setSelected(member),
        disabled: busy,
      },
    ];
    if (!canManage) return actions;
    actions.push({
      label: `Editar rol de ${member.email}`,
      icon: Pencil,
      onClick: () => setEditing(member),
      disabled: busy,
      busy,
    });
    if (member.status === "active") {
      actions.push({
        label: `Desactivar a ${member.email}`,
        tooltip: selfDeactivation
          ? "No podés desactivar tu propia membresía."
          : undefined,
        icon: UserRoundX,
        onClick: () => setDeactivating(member),
        disabled: busy || selfDeactivation,
        busy,
      });
    } else {
      actions.push({
        label: `Reactivar a ${member.email}`,
        icon: UserRoundCheck,
        onClick: () => setReactivating(member),
        disabled: busy,
        busy,
      });
    }
    return actions;
  };
  const rows = (member: api.Member) => (
    <TableRow key={member.user_id}>
      <TableCell>{member.email}</TableCell>
      <TableCell>
        <Badge>{roleLabels[member.role]}</Badge>
      </TableCell>
      <TableCell>
        <Badge>{statusLabels[member.status]}</Badge>
      </TableCell>
      <TableCell>
        <Badge>{passwordLabel(member)}</Badge>
      </TableCell>
      <TableCell className="actions-cell">
        <RowActions actions={actionsFor(member)} />
      </TableCell>
    </TableRow>
  );
  return (
    <section className="users-directory">
      <div className="page-header">
        <div>
          <h1>Personas</h1>
          <p className="muted">
            Administrá quién puede acceder a este espacio de trabajo.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus data-icon="inline-start" />
            Nuevo
          </Button>
        )}
      </div>
      {success && (
        <p className="notice" role="status">
          {success}
        </p>
      )}
      {mutationError && (
        <p className="notice error" role="alert">
          {mutationError}
        </p>
      )}
      <form className="directory-toolbar" onSubmit={searchSubmit}>
        <label className="search-field">
          <span className="sr-only">Buscar por correo electrónico</span>
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por correo electrónico"
          />
        </label>
        <Button
          type="button"
          variant="outline"
          aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          Filtros <ChevronDown />
        </Button>
        <Button type="submit">Buscar</Button>
        {filtersOpen && (
          <div className="filters">
            <label>
              Rol
              <select
                value={query.role}
                onChange={(event) =>
                  update({
                    role: event.target.value as api.MembersQuery["role"],
                    page: 1,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="admin">Administración</option>
                <option value="member">Integrante</option>
                <option value="viewer">Consulta</option>
              </select>
            </label>
            <label>
              Estado
              <select
                value={query.status}
                onChange={(event) =>
                  update({
                    status: event.target.value as api.MembersQuery["status"],
                    page: 1,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="active">Activo</option>
                <option value="inactive">Inactivo</option>
              </select>
            </label>
            <label>
              Ordenar por
              <select
                value={query.sort}
                onChange={(event) =>
                  update({ sort: event.target.value, page: 1 })
                }
              >
                <option value="email:asc">Email ascendente</option>
                <option value="email:desc">Email descendente</option>
                <option value="role:asc">Rol ascendente</option>
                <option value="role:desc">Rol descendente</option>
                <option value="status:asc">Estado ascendente</option>
                <option value="status:desc">Estado descendente</option>
                <option value="created_at:asc">Fecha de alta ascendente</option>
                <option value="created_at:desc">
                  Fecha de alta descendente
                </option>
              </select>
            </label>
          </div>
        )}
      </form>
      {loading ? (
        <>
          <p className="sr-only">Cargando personas</p>
          <div className="desktop-table-loading">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
          <div className="member-cards">
            {[1, 2, 3].map((key) => (
              <article className="member-card" key={key}>
                <Skeleton />
                <Skeleton />
              </article>
            ))}
          </div>
        </>
      ) : error ? (
        <section className="notice error" role="alert">
          <p>{error}</p>
          <Button
            variant="outline"
            onClick={() => {
              setError("");
              setLoading(true);
              setRetry((value) => value + 1);
            }}
          >
            Reintentar
          </Button>
        </section>
      ) : (
        result && (
          <>
            <div className="desktop-table">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Correo electrónico</TableHead>
                    <TableHead>Rol</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Configuración</TableHead>
                    <TableHead className="actions-cell">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>{result.items.map(rows)}</TableBody>
              </Table>
            </div>
            <div className="member-cards">
              {result.items.map((member) => (
                <article className="member-card" key={member.user_id}>
                  <strong>{member.email}</strong>
                  <div>
                    <MemberLabels member={member} />
                  </div>
                  <RowActions actions={actionsFor(member)} />
                </article>
              ))}
            </div>
            {result.items.length === 0 ? (
              <section className="notice">
                No hay personas que coincidan con los filtros.
              </section>
            ) : (
              <Pagination result={result} update={update} />
            )}
          </>
        )
      )}
      <DetailsDialog
        member={selected}
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      />
      {canManage && (
        <>
          <EditRoleDialog
            key={editing?.user_id ?? "none"}
            member={editing}
            open={!!editing}
            busy={pendingMemberId === editing?.user_id}
            onOpenChange={(open) => !open && setEditing(null)}
            onSubmit={(role) =>
              mutateMember(editing!, { role }, "El rol fue actualizado.")
            }
          />
          <ConfirmDialog
            open={!!deactivating}
            onOpenChange={(open) => !open && setDeactivating(null)}
            title={`¿Querés desactivar a ${deactivating?.email ?? "esta persona"}?`}
            description={`${deactivating?.email ?? "Esta persona"} dejará de tener acceso al espacio de trabajo.`}
            confirmLabel="Desactivar"
            destructive
            onConfirm={() =>
              mutateMember(
                deactivating!,
                { active: false },
                "La persona fue desactivada.",
              )
            }
          />
          <ConfirmDialog
            open={!!reactivating}
            onOpenChange={(open) => !open && setReactivating(null)}
            title={`¿Querés reactivar a ${reactivating?.email ?? "esta persona"}?`}
            description={`${reactivating?.email ?? "Esta persona"} recuperará el acceso al espacio de trabajo.`}
            confirmLabel="Reactivar"
            onConfirm={() =>
              mutateMember(
                reactivating!,
                { active: true },
                "La persona fue reactivada.",
              )
            }
          />
          <CreateDialog
            open={createOpen}
            onOpenChange={setCreateOpen}
            onCreated={(message) => {
              setSuccess(message);
              setCreateOpen(false);
              setLoading(true);
              setRetry((value) => value + 1);
            }}
          />
        </>
      )}
    </section>
  );
}
