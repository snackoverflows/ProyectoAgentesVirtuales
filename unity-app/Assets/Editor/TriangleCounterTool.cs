using UnityEngine;
using UnityEditor;

public static class TriangleCounterTool
{
    [MenuItem("Tools/Count Selected Avatar Triangles")]
    public static void CountSelected()
    {
        GameObject selected = Selection.activeGameObject;

        if (selected == null)
        {
            Debug.LogWarning("Seleccioná el root del prefab/avatar primero.");
            return;
        }

        int totalTris = 0;
        int totalVerts = 0;

        foreach (var smr in selected.GetComponentsInChildren<SkinnedMeshRenderer>(true))
        {
            if (smr.sharedMesh == null) continue;

            totalTris += smr.sharedMesh.triangles.Length / 3;
            totalVerts += smr.sharedMesh.vertexCount;
        }

        foreach (var mf in selected.GetComponentsInChildren<MeshFilter>(true))
        {
            if (mf.sharedMesh == null) continue;

            totalTris += mf.sharedMesh.triangles.Length / 3;
            totalVerts += mf.sharedMesh.vertexCount;
        }

        Debug.Log($"{selected.name} → Triángulos: {totalTris} | Vértices: {totalVerts}");
    }
}