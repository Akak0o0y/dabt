import { COOKIE_NAME } from "@shared/const";
import { z } from "zod";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { adminProcedure, protectedProcedure, publicProcedure, router } from "./_core/trpc";
import { evaluateDabt, getDabtComplianceMap } from "./dabt";
import { getAuditEvidence, listAuditEvidence, persistAuditEvidence } from "./evidence";
import { approveAuditEvidence, getEvidenceReview } from "./review";

const dabtEvaluationInput = z.object({
  document: z.string().min(1).max(100_000),
  agentId: z.string().max(128).optional(),
  purpose: z.string().max(256).optional(),
  lawfulBasis: z.string().max(128).optional(),
  crossBorder: z.boolean().optional(),
  sector: z.string().max(128).optional(),
  eventType: z.string().max(128).optional(),
  agentAuthorised: z.boolean().optional(),
  requiresMinimisation: z.boolean().optional(),
});

export const appRouter = router({
    // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),
  dabt: router({
    evaluate: publicProcedure
      .input(dabtEvaluationInput)
      .mutation(({ input }) => evaluateDabt(input)),
    evaluateAndPersist: protectedProcedure
      .input(dabtEvaluationInput)
      .mutation(async ({ ctx, input }) => {
        const evaluation = await evaluateDabt(input);
        const snapshot = await persistAuditEvidence(ctx.user.id, input.document, evaluation as never);
        return { evaluation, snapshot };
      }),
    evidenceList: protectedProcedure
      .input(z.object({ limit: z.number().int().min(1).max(100).default(20) }))
      .query(({ ctx, input }) => listAuditEvidence(ctx.user.id, input.limit)),
    evidenceGet: protectedProcedure
      .input(z.object({ id: z.string().min(1).max(64) }))
      .query(({ ctx, input }) => getAuditEvidence(ctx.user.id, input.id)),
    evidenceReviewGet: protectedProcedure
      .input(z.object({ evidenceSnapshotId: z.string().min(1).max(64) }))
      .query(({ ctx, input }) => getEvidenceReview(ctx.user.id, input.evidenceSnapshotId)),
    reviewEvidence: adminProcedure
      .input(z.object({
        evidenceSnapshotId: z.string().min(1).max(64),
        disposition: z.enum(["approved", "rejected"]),
        rationaleEn: z.string().min(20).max(4_000),
        rationaleAr: z.string().min(12).max(4_000),
      }))
      .mutation(({ ctx, input }) => approveAuditEvidence({ ...input, reviewerUserId: ctx.user.id })),
    complianceMap: publicProcedure.query(() => getDabtComplianceMap()),
  }),

  // TODO: add feature routers here, e.g.
  // todo: router({
  //   list: protectedProcedure.query(({ ctx }) =>
  //     db.getUserTodos(ctx.user.id)
  //   ),
  // }),
});

export type AppRouter = typeof appRouter;
