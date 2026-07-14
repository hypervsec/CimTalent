import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { jobsApi } from "../api/jobs";
const schema = z.object({
  company_name: z.string().min(1, "Şirket zorunlu"),
  title: z.string().min(1, "Pozisyon zorunlu"),
  description_raw: z.string().min(10, "Açıklama en az 10 karakter"),
  city: z.string().optional(),
  country: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;
export function JobFormPage() {
  const navigate = useNavigate();
  const form = useForm<FormValues>({ resolver: zodResolver(schema) });
  const mutation = useMutation({
    mutationFn: (values: FormValues) => jobsApi.create({ ...values, source: "manual" }),
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
  });
  return (
    <section>
      <h2>Yeni ilan</h2>
      <form onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        {(["company_name", "title", "description_raw", "city", "country"] as const).map((name) => (
          <label key={name}>
            {name}
            <textarea {...form.register(name)} />
            {form.formState.errors[name] && <small>{form.formState.errors[name]?.message}</small>}
          </label>
        ))}
        <button type="submit" disabled={mutation.isPending}>
          Kaydet
        </button>
      </form>
    </section>
  );
}
